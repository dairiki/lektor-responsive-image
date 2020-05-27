# -*- coding: utf-8 -*-
from functools import wraps
import inspect
try:
    from urllib.parse import urlparse
except ImportError:             # pragma: no cover
    from urlparse import urlparse

from lektor.context import get_ctx
from lektor.db import Image
from lektor.pluginsystem import (
    Plugin,
    get_plugin,
    )
from lektor.utils import join_path
from markupsafe import escape
from werkzeug.utils import cached_property


def ignore_unsupported_kwargs(f):
    getargspec = inspect.getfullargspec if hasattr(inspect, 'getfullargspec') \
                 else inspect.getargspec
    supported_args = getargspec(f).args

    @wraps(f)
    def wrapped(*args, **kwargs):
        supported_kwargs = set(supported_args[len(args):]).intersection(kwargs)
        return f(*args, **{k: kwargs[k] for k in supported_kwargs})
    return wrapped


def fmt_attrs(attrs):
    return ' '.join('{}="{}"'.format(key, escape(val))
                    for key, val in attrs.items()
                    if val is not None)


class ResponsiveImage(object):
    DEFAULT_CONFIG = {
        'widths': [480, 800, 1200, 2400],
        'quality': 92,
        'default_width': 1200,
        'sizes': None,
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
            attrs['srcset'] = self.srcset
            if self.sizes is not None:
                attrs['sizes'] = self.sizes
        return attrs

    @cached_property
    def srcset(self):
        url_to = self.ctx.url_to
        widths = list(self.iter_widths())
        if len(widths) > 1:
            def image_info(width):
                image = self.resize_image(width)
                return "{url} {width}w".format(url=url_to(image), width=width)
            return ', '.join(map(image_info, self.iter_widths()))

    @property
    def sizes(self):
        return self.config.get('sizes')

    def iter_widths(self):
        image_width = self.image.width
        widths = self.config.get('widths', [])
        for w in widths:
            if w < image_width:
                yield w
            else:
                yield image_width
                break

    def default_image_attrs(self):
        default_width = self.config.get('default_width', 800)
        default_image = self.resize_image(default_width)
        return {
            'src': self.ctx.url_to(default_image),
            'width': default_image.width,
            'height': default_image.height,
            }

    def resize_image(self, width):
        image = self.image
        if width is None or width >= image.width:
            return image
        # We (should) never upscale.  Upscale=True is passed here
        # solely to avoid triggering a deprecation warning.
        thumbnail = ignore_unsupported_kwargs(self.image.thumbnail)
        return thumbnail(width, quality=self.config['quality'], upscale=True)


def resolve_image(record, src):
    if record is None:
        return None
    url = urlparse(src)
    if url.scheme or url.netloc:
        return None

    path = url.path
    if not path.startswith('/'):
        assert record.path is not None   # FIXME: better error reporting?
        path = join_path(record.path, path)
    source = record.pad.get(path)
    if isinstance(source, Image):
        return source


class ResponsiveImageMixin(object):
    """Render markdown images at responsive resolutions (using srcset).

    """

    def image(self, src, title, text):
        image = resolve_image(self.record, src)
        if image is not None and image.format in ('png', 'gif', 'jpeg'):
            plugin = get_plugin('responsive-image', env=self.record.pad.env)
            attrs = {'alt': text, 'title': title or None}
            attrs.update(plugin.responsive_image(image).attrs)
            return "<img {}>".format(fmt_attrs(attrs))
        else:
            return super(ResponsiveImageMixin, self).image(src, title, text)


class ResponsiveImagePlugin(Plugin):
    name = 'Responsive Image'
    description = u'Support for responsive-resolutioned images.'

    def on_setup_env(self, **extra):
        self.env.jinja_env.globals['responsive_image'] = self.responsive_image

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
    def _parse_ini(inifile, section='default'):
        data = inifile.section_as_dict(section)
        config = {}
        if 'widths' in data:
            try:
                config['widths'] = list(map(int, data['widths'].split()))
            except ValueError:
                pass
        for key in ('quality', 'default_width'):
            if key in data:
                try:
                    config[key] = int(data[key])
                except ValueError:
                    pass
        if 'sizes' in data:
            config['sizes'] = data['sizes']
        return config
