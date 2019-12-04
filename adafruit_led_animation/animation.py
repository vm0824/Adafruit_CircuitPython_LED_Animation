# The MIT License (MIT)
#
# Copyright (c) 2019 Kattni Rembor for Adafruit Industries
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""
`adafruit_led_animation.animation`
================================================================================

CircuitPython helper library for LED animations.


* Author(s): Roy Hooper, Kattni Rembor

Implementation Notes
--------------------

**Hardware:**

* `Adafruit NeoPixels <https://www.adafruit.com/category/168>`_
* `Adafruit DotStars <https://www.adafruit.com/category/885>`_

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads

"""

try:
    from time import monotonic_ns as monotonic_ns, sleep
except ImportError:
    import time

    def monotonic_ns():
        """
        Implementation of monotonic_ns for platforms without time.monotonic_ns
        """
        return int(time.time() * 1000000000)

import random
from .color import BLACK, RAINBOW

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_LED_Animation.git"


class Animation:
    """
    Base class for animations.
    """
    def __init__(self, pixel_object, speed, color, peers=None):
        self.pixel_object = pixel_object
        self._speed_ns = 0
        self.speed = speed  # sets _speed_ns
        self._color = color
        self._next_update = monotonic_ns()
        self.pixel_object.auto_write = False
        self.color = color
        self.peers = peers if peers else []

    def animate(self):
        """
        Call animate() from your code's main loop.  It will draw the animation draw() at intervals
        configured by the speed property (set from init).
        :return: True if the animation draw cycle was triggered, otherwise False.
        """
        now = monotonic_ns()
        if now < self._next_update:
            return False

        self.draw()
        if self.peers:
            for peer in self.peers:
                peer.draw()
        self.show()
        for peer in self.peers:
            peer.show()

        self._next_update = now + self._speed_ns
        return True

    def _next_update_time(self):
        if self._slave_of:
            return self._slave_of

    def draw(self):
        """
        Animation subclasses must implement draw() to render the animation sequence.
        """

    def show(self):
        """
        Displays the updated pixels.  Called during animates with changes.
        """
        self.pixel_object.show()

    @property
    def color(self):
        """
        The current color.
        """
        return self._color

    @color.setter
    def color(self, color):
        if isinstance(color, int):
            color = (color >> 16 & 0xff, color >> 8 & 0xff, color & 0xff)
        self._color = color
        self._recompute_color(color)

    @property
    def speed(self):
        """
        The animation speed in fractional seconds.
        """
        return self._speed_ns / 1000000000

    @speed.setter
    def speed(self, seconds):
        self._speed_ns = int(seconds * 1000000000)

    def _recompute_color(self, color):
        pass

    def change_color(self, color):
        """
        By default changing color uses the color property.
        """
        self.color = color


class ColorCycle(Animation):
    """
    Animate a sequence of one or more colors, cycling at the specified speed.

    :param pixel_object: The initialised LED object.
    :param int speed: Animation speed in seconds, e.g. ``0.1``.
    :param colors: A list of colors to cycle through in ``(r, g, b)`` tuple, or ``0x000000`` hex
                   format. Defaults to a rainbow color cycle.
    """
    def __init__(self, pixel_object, speed, colors=RAINBOW):
        self.colors = colors
        super(ColorCycle, self).__init__(pixel_object, speed, colors[0])
        self._generator = self._color_generator()

    def draw(self):
        next(self._generator)
        self.pixel_object.fill(self.color)
        self.show()

    def _color_generator(self):
        index = 0
        while True:
            self._color = self.colors[index]
            yield
            index = (index + 1) % len(self.colors)

    def change_color(self, color):
        """
        ColorCycle doesn't support change_color.
        """


class Blink(ColorCycle):
    """
    Blink a color on and off.

    :param pixel_object: The initialised LED object.
    :param int speed: Animation speed in seconds, e.g. ``0.1``.
    :param color: Animation color in ``(r, g, b)`` tuple, or ``0x000000`` hex format.
    """
    def __init__(self, pixel_object, speed, color):
        super(Blink, self).__init__(pixel_object, speed, [color, BLACK])

    def _recompute_color(self, color):
        self.colors = [color, BLACK]

    def change_color(self, color):
        """
        Change the color.
        """
        self.colors[0] = color


class Solid(ColorCycle):
    """
    A solid color.

    :param pixel_object: The initialised LED object.
    :param color: Animation color in ``(r, g, b)`` tuple, or ``0x000000`` hex format.
    """
    def __init__(self, pixel_object, color):
        super(Solid, self).__init__(pixel_object, speed=1, colors=[color])

    def _recompute_color(self, color):
        self.colors = [color]

    def change_color(self, color):
        """
        Change the color.
        """
        self.colors[0] = color


class Comet(Animation):
    """
    A comet animation.

    :param pixel_object: The initialised LED object.
    :param int speed: Animation speed in seconds, e.g. ``0.1``.
    :param color: Animation color in ``(r, g, b)`` tuple, or ``0x000000`` hex format.
    :param int tail_length: The length of the comet. Defaults to 10. Cannot exceed the number of
                            pixels present in the pixel object, e.g. if the strip is 30 pixels
                            long, the ``tail_length`` cannot exceed 30 pixels.
    """
    def __init__(self, pixel_object, speed, color, tail_length=10, reverse=False):
        self._tail_length = tail_length + 1
        self._color_step = 0.9 / tail_length
        self._color_offset = 0.1
        self._comet_colors = None
        self.reverse = reverse
        super(Comet, self).__init__(pixel_object, speed, color)
        self._generator = self._comet_generator()

    def _recompute_color(self, color):
        self._comet_colors = [BLACK] + [
            [int(color[rgb] * ((n * self._color_step) + self._color_offset))
             for rgb in range(len(color))
            ] for n in range(self._tail_length - 1)
        ]
        self._reverse_comet_colors = list(reversed(self._comet_colors))

    def _get_range(self, num_pixels):
        if self.reverse:
            return range(num_pixels, -self._tail_length - 1, -1)
        return range(-self._tail_length, num_pixels + 1)

    def _comet_generator(self):
        num_pixels = len(self.pixel_object)
        while True:
            colors = self._reverse_comet_colors if self.reverse else self._comet_colors
            for start in self._get_range(num_pixels):

                if start + self._tail_length < num_pixels:
                    end = self._tail_length
                else:
                    end = num_pixels - start
                if start <= 0:
                    num_visible = self._tail_length + start
                    self.pixel_object[0:num_visible] = colors[self._tail_length - num_visible:]
                else:
                    self.pixel_object[start:start + end] = colors[0:end]
                self.show()
                yield

    def draw(self):
        next(self._generator)


class Sparkle(Animation):
    """
    Sparkle animation of a single color.

    :param pixel_object: The initialised LED object.
    :param int speed: Animation speed in seconds, e.g. ``0.1``.
    :param color: Animation color in ``(r, g, b)`` tuple, or ``0x000000`` hex format.
    """
    def __init__(self, pixel_object, speed, color):
        self._half_color = None
        self._dim_color = None
        super(Sparkle, self).__init__(pixel_object, speed, color)

    def _recompute_color(self, color):
        half_color = tuple(color[rgb] // 4 for rgb in range(len(color)))
        dim_color = tuple(color[rgb] // 10 for rgb in range(len(color)))
        for pixel in range(len(self.pixel_object)):
            if self.pixel_object[pixel] == self._half_color:
                self.pixel_object[pixel] = half_color
            elif self.pixel_object[pixel] == self._dim_color:
                self.pixel_object[pixel] = dim_color
        self._half_color = half_color
        self._dim_color = dim_color

    def draw(self):
        pixel = random.randint(0, (len(self.pixel_object) - 2))
        self.pixel_object[pixel] = self._color
        self.show()
        self.pixel_object[pixel] = self._half_color
        self.pixel_object[pixel + 1] = self._dim_color
        self.show()


class AnimationSequence:
    """
    A sequence of Animations to run in sequence, looping forever.
    Advances manually or at the specified interval.
    """
    def __init__(self, *members, advance_interval=None):
        self._members = members
        self._advance_interval = advance_interval * 1000000000 if advance_interval else None
        self._last_advance = monotonic_ns()
        self._current = 0

    def _auto_advance(self):
        if not self._advance_interval:
            return
        now = monotonic_ns()
        if self._last_advance - now > self._advance_interval:
            self._last_advance = now
            self.next()

    def next(self):
        self._current = (self._current + 1) % len(self._members)

    def animate(self):
        self._auto_advance()
        self.current_animation.animate()

    @property
    def current_animation(self):
        return self._members[self._current]

    def change_color(self, color):
        """
        Change the color of all members that support setting the color with change_color.
        Ignored by animations that do not support it.
        """
        for item in self._members:
            item.change_color(color)


class AnimationGroup:
    """
    A group of animations that are active together, such as a strip of
    pixels connected to and the onboard NeoPixels on a CPX or CPB.
    """
    def __init__(self, *members, sync=False):
        self._members = members
        self._sync = sync
        if sync:
            main = members[0]
            main.peers = members[1:]

    def animate(self):
        if self._sync:
            return self._members[0].animate()

        return any([item.animate() for item in self._members])

    def change_color(self, color):
        """
        Change the color of all members that support setting the color with change_color.
        Ignored by animations that do not support it.
        """
        for item in self._members:
            item.change_color(color)
