# Lektor Responsive Images Plugin

[![PyPI version](https://img.shields.io/pypi/v/lektor-responsive-image.svg)](https://pypi.org/project/lektor-responsive-image/)
[![PyPI Supported Python Versions](https://img.shields.io/pypi/pyversions/lektor-responsive-image.svg)](https://pypi.python.org/pypi/lektor-responsive-image/)
[![GitHub license](https://img.shields.io/github/license/dairiki/lektor-responsive-image)](https://github.com/dairiki/lektor-responsive-image/blob/master/LICENSE)
[![GitHub Actions (Tests)](https://github.com/dairiki/lektor-responsive-image/workflows/Tests/badge.svg)](https://github.com/dairiki/lektor-responsive-image/actions)

This plugin hacks up Lektor’s Markdown renderer to support
multi-resolution responsive images in Markdown text.

Local images will be resized to a variety of sizes, and `<img>` tags
will be rendered with `srcset` and (optionally) `sizes` attributes in
order to support the use of [responsive image
resolutions][mdn-responsive-images].

This plugin also registers a Jinja global function, `responsive_image`,
which can be used to render markup for multi-resolution images from
Jinja templates.

[mdn-responsive-images]: <https://developer.mozilla.org/en-US/docs/Learn/HTML/Multimedia_and_embedding/Responsive_images>
    "MDN: Responsive Images"

## Configuration

The plugin is configured through `configs/responsive-images.ini`.
Here is an annotated example:

```ini
# Currently, only a section named "default" is used
[default]

# Widths of images to generate.
#
# Images will be generated at these widths (but only up to the native
# width of the image.)
#
# (This is the default value.)
widths = 480 800 1200 2400

# Image quality for generating scaled images
# (This is the default value.)
# NOTE: the quality parameter will be ignored if running under lektor version
# before 3.1.
quality = 92

# Width of the image put into the `src` attribute of the `<img>` tag.
# (Though the orignal image is never up-scaled.  If the original is narrower than
# this width, then the original image is used.)
# (This is the default value.)
default_width = 1200

# Value put into the `sizes` attribute of the `<img>` tag.
# The default is not to set a `sizes` attribute
sizes = (max-width: 576px) 95vw, (max-width: 992px) 65vw, 800px
```

## Usage

In the common use case, you will want to adjust the CSS stylesheet for
your site so that images within Markdown text get either `display:
block` or `display: inline-block`, along with `max-width: 100%`, or
similar.

## Jinja global function

This plugin also registers a Jinja global function named `responsive_image`.
It expects a single argument, which should be an `Image` instance.
It returns an object which has an `.attr` attribute whose value is
a dict of attribute which could be set on an `<img>` tag to generate
markup for a multi-resolution image.  E.g.

```html+jinja
{% set image = this.attachments.get('figure.png') %}
{% set img_attrs = responsive_image(image).attrs %}
<figure class="figure">
  <img class="figure-img" {{ img_attrs|xmlattr }}>
  <figcaption class="figure-caption text-center">
    {{- this.caption -}}
  </figcaption>
</figure>
```

## Author

Jeff Dairiki <dairiki@dairiki.org>










