import sys
from urllib.parse import urlparse

import mistune
from lektor.context import get_ctx
from lektor.db import Image
from lektor.pluginsystem import get_plugin
from lektor.pluginsystem import Plugin
from lektor.utils import join_path
from markupsafe import escape
from werkzeug.utils import cached_property

HAVE_MISTUNE0 = mistune.__version__.startswith("0.")

try:
    from lektor.markdown import controller_class
except ImportError:
    # Lektor < 3.4
    from lektor.markdown import ImprovedRenderer
    from lektor.markdown import MarkdownConfig
else:
    # Lektor >= 3.4
    _mistune_module = sys.modules[controller_class.__module__]
    ImprovedRenderer = _mistune_module.ImprovedRenderer
    MarkdownConfig = _mistune_module.MarkdownConfig


def fmt_attrs(attrs):
    """Format a dict to markup suitable for use as HTML tag attributes."""
    return " ".join(
        f'{key}="{escape(val)}"' for key, val in attrs.items() if val is not None
    )


class ResponsiveImage:
    """Helper class to compute attributes for multi-resolution responsive images."""

    DEFAULT_CONFIG = {
        "widths": [480, 800, 1200, 2400],
        "quality": 92,
        "default_width": 1200,
        "sizes": None,
    }

    def __init__(self, image, config=None, ctx=None):
        if config is None:
            config = self.DEFAULT_CONFIG.copy()
        if ctx is None:
            ctx = get_ctx()
        self.config = config
        self.image = image
        self.ctx = ctx

    @property
    def attrs(self):
        attrs = self.default_image_attrs()
        if self.srcset is not None:
            attrs["srcset"] = self.srcset
            if self.sizes is not None:
                attrs["sizes"] = self.sizes
        return attrs

    @cached_property
    def srcset(self):
        url_to = self.ctx.url_to
        widths = list(self.iter_widths())
        if len(widths) > 1:

            def image_info(width):
                image = self.resize_image(width)
                return f"{url_to(image)} {width}w"

            return ", ".join(map(image_info, self.iter_widths()))

    @property
    def sizes(self):
        return self.config.get("sizes")

    def iter_widths(self):
        image_width = self.image.width
        widths = self.config.get("widths", [])
        for w in widths:
            if w < image_width:
                yield w
            else:
                yield image_width
                break

    def default_image_attrs(self):
        default_width = self.config.get("default_width", 800)
        default_image = self.resize_image(default_width)
        return {
            "src": self.ctx.url_to(default_image),
            "width": default_image.width,
            "height": default_image.height,
        }

    def resize_image(self, width):
        image = self.image
        if width is None or width >= image.width:
            return image
        # We (should) never upscale.  Upscale=True is passed here
        # solely to avoid triggering a deprecation warning.
        return self.image.thumbnail(width, quality=self.config["quality"], upscale=True)


def resolve_image(record, src):
    """Resolve local image URL to Lektor Image record."""
    if record is None:
        return None
    url = urlparse(src)
    if url.scheme or url.netloc:
        return None

    path = url.path
    if not path.startswith("/"):
        assert record.path is not None  # FIXME: better error reporting?
        path = join_path(record.path, path)
    source = record.pad.get(path)
    if isinstance(source, Image):
        return source


class ResponsiveImageMixin:
    """Markdown renderer mixin to render local images at multiple resolutions."""

    def image(self, src, *args):
        # Under Lektor >= 3.4, the record is available at self.lektor.record.
        # Prior to that, it's at self.record.
        renderer_helper = getattr(self, "lektor", self)
        record = renderer_helper.record

        image = resolve_image(record, src)
        if image is not None and image.format in ("png", "gif", "jpeg"):
            alt, title = reversed(args) if HAVE_MISTUNE0 else args
            attrs = {"alt": alt, "title": title or None}
            plugin = get_plugin("responsive-image", env=record.pad.env)
            attrs.update(plugin.responsive_image(image).attrs)
            return f"<img {fmt_attrs(attrs)}>"
        else:
            return super().image(src, *args)


class ResponsiveImagePlugin(Plugin):
    name = "Responsive Image"
    description = "Support for multi-resolution responsive images."

    def on_setup_env(self, **extra):
        self.env.jinja_env.globals["responsive_image"] = self.responsive_image

    def on_markdown_config(self, config, **extra):
        config.renderer_mixins.append(ResponsiveImageMixin)

    def responsive_image(self, image):
        config = self.get_responsive_image_config()
        return ResponsiveImage(image, config)

    def get_responsive_image_config(self):
        inifile = self.get_config()
        config = ResponsiveImage.DEFAULT_CONFIG.copy()
        config.update(self._parse_ini(inifile))
        return config

    @staticmethod
    def _parse_ini(inifile, section="default"):
        data = inifile.section_as_dict(section)
        config = {}
        if "widths" in data:
            try:
                config["widths"] = list(map(int, data["widths"].split()))
            except ValueError:
                pass
        for key in ("quality", "default_width"):
            if key in data:
                try:
                    config[key] = int(data[key])
                except ValueError:
                    pass
        if "sizes" in data:
            config["sizes"] = data["sizes"]
        return config
