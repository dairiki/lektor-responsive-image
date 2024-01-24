import re
from contextlib import ExitStack

import pytest
from inifile import IniFile

from lektor_responsive_image import HAVE_MISTUNE0
from lektor_responsive_image import ImprovedRenderer
from lektor_responsive_image import MarkdownConfig
from lektor_responsive_image import resolve_image
from lektor_responsive_image import ResponsiveImage
from lektor_responsive_image import ResponsiveImageMixin
from lektor_responsive_image import ResponsiveImagePlugin

try:
    from lektor.markdown.controller import RendererContext
except ModuleNotFoundError:
    RendererContext = None


class DummyImage:
    def __init__(self, width, height, format="jpeg", quality=None):
        self.width = width
        self.height = height
        self.format = format
        self.quality = quality

    def thumbnail(self, width, quality=None, upscale=None):
        height = int(self.height * width / self.width + 0.5)
        return DummyImage(width, height, format=self.format, quality=quality)


class DummyContext:
    def url_to(self, image):
        return f"img-{image.width}.jpg"


class TestResponsiveImage:
    @pytest.fixture
    def width(self):
        return 2400

    @pytest.fixture
    def image(self, width):
        height = int(3 * width / 4)
        return DummyImage(width, height)

    @pytest.fixture
    def sizes(self):
        return None

    @pytest.fixture
    def resp_image(self, image, sizes):
        config = ResponsiveImage.DEFAULT_CONFIG.copy()
        config["sizes"] = sizes
        return ResponsiveImage(image, config, ctx=DummyContext())

    def test_init_no_config(self, image):
        resp_image = ResponsiveImage(image)
        assert resp_image.config == ResponsiveImage.DEFAULT_CONFIG
        assert resp_image.config is not ResponsiveImage.DEFAULT_CONFIG

    @pytest.mark.parametrize("width", [480])
    def test_attrs_no_srcset(self, resp_image):
        assert "srcset" not in resp_image.attrs

    @pytest.mark.parametrize("width", [800])
    def test_attrs_srcset(self, resp_image):
        srcset = resp_image.attrs["srcset"]
        assert srcset == "img-480.jpg 480w, img-800.jpg 800w"

    @pytest.mark.parametrize("sizes", [None])
    def test_attrs_no_sizes(self, resp_image):
        assert "sizes" not in resp_image.attrs

    @pytest.mark.parametrize("sizes", ["600px"])
    def test_attrs_sizes(self, resp_image, sizes):
        assert resp_image.attrs["sizes"] == sizes

    @pytest.mark.parametrize("sizes", ["50vw", None])
    def test_sizes(self, resp_image, sizes):
        assert resp_image.sizes == sizes

    @pytest.mark.parametrize(
        "width, widths",
        [
            (120, [120]),
            (480, [480]),
            (1024, [480, 800, 1024]),
            (3600, [480, 800, 1200, 2400]),
        ],
    )
    def test_iter_widths(self, resp_image, widths):
        assert list(resp_image.iter_widths()) == widths

    def test_default_image_attrs(self, resp_image):
        assert resp_image.default_image_attrs() == {
            "width": 1200,
            "height": 900,
            "src": "img-1200.jpg",
        }

    def test_resize_image(self, resp_image, image):
        assert resp_image.resize_image(image.width) is image
        assert resp_image.resize_image(image.width + 1) is image
        resized = resp_image.resize_image(image.width - 1)
        assert resized.width == image.width - 1
        assert resized.quality == 92


class Test_resolve_image:
    def test_no_record(self):
        assert resolve_image(None, "test.jpg") is None

    def test_external_url(self, lektor_pad):
        assert resolve_image(lektor_pad.root, "http://example.com/test.jpg") is None

    def test_not_image(self, lektor_pad):
        assert resolve_image(lektor_pad.root, "dummy.pdf") is None

    def test_resolve(self, lektor_pad):
        image = resolve_image(lektor_pad.root, "test.jpg")
        assert image.path == "/test.jpg"
        assert image.width == 800

    def test_resolve_absolute(self, lektor_pad):
        about = lektor_pad.get("/about")
        image = resolve_image(about, "/test.jpg")
        assert image.path == "/test.jpg"

    def test_resolve_relative(self, lektor_pad):
        about = lektor_pad.get("/about")
        image = resolve_image(about, "../test.jpg")
        assert image.path == "/test.jpg"


@pytest.fixture
def load_plugin(lektor_env):
    lektor_env.plugin_controller.instanciate_plugin(
        "responsive-image", ResponsiveImagePlugin
    )


class RendererWithMixin(ResponsiveImageMixin, ImprovedRenderer):
    pass


class TestResponsiveImageMixin:
    @pytest.fixture
    def record(self, lektor_pad):
        return lektor_pad.root

    @pytest.fixture
    def mixin(self, record):
        with ExitStack() as stack:
            renderer = RendererWithMixin()
            if RendererContext is not None:
                stack.enter_context(RendererContext(record, meta={}, field_options={}))
            else:  # lektor < 3.4
                renderer.record = record
            yield renderer

    @pytest.mark.usefixtures("load_plugin", "lektor_context")
    def test(self, mixin):
        args = ("TITLE", "ALT") if HAVE_MISTUNE0 else ("ALT", "TITLE")
        img = mixin.image("test.jpg", *args)
        assert re.match(r"<img.*>", img)
        assert 'alt="ALT"' in img
        assert "srcset=" in img

    @pytest.mark.usefixtures("load_plugin", "lektor_context")
    def test_not_resolvable(self, mixin):
        args = ("TITLE", "ALT") if HAVE_MISTUNE0 else ("ALT", "TITLE")
        img = mixin.image("foo.jpg", *args)
        assert re.match(r"<img.*>", img)
        assert 'alt="ALT"' in img
        assert "srcset=" not in img


class TestResponsiveImagePlugin:
    @pytest.fixture
    def plugin(self, lektor_env):
        return ResponsiveImagePlugin(lektor_env, "responsive-image")

    def test_on_setup_env(self, plugin, lektor_env):
        plugin.on_setup_env()
        jinja_globals = lektor_env.jinja_env.globals
        assert "responsive_image" in jinja_globals

    def test_on_markdown_config(self, plugin):
        config = MarkdownConfig()
        plugin.on_markdown_config(config)
        assert config.renderer_mixins == [ResponsiveImageMixin]

    def test_get_responsive_image_config(self, plugin):
        config = plugin.get_responsive_image_config()
        assert config == ResponsiveImage.DEFAULT_CONFIG
        assert config is not ResponsiveImage.DEFAULT_CONFIG

    @pytest.fixture
    def inifile(self, config, tmp_path):
        ini = IniFile(str(tmp_path / "test.ini"))
        for key, value in config.items():
            ini["default." + key] = value
        ini.save()
        return ini

    @pytest.mark.parametrize(
        "config, expected",
        [
            ({"widths": "10 20 "}, {"widths": [10, 20]}),
            ({"widths": "10-20"}, {}),
            ({"quality": "12"}, {"quality": 12}),
            ({"quality": "twelve"}, {}),
            ({"default_width": "10"}, {"default_width": 10}),
            ({"sizes": "60vw"}, {"sizes": "60vw"}),
        ],
    )
    def test__parse_ini(self, plugin, inifile, expected):
        assert plugin._parse_ini(inifile) == expected
