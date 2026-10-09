# Schematic renderer provenance

Circuit Atlas Schematic Studio is an in-repository implementation, not a fork or
an executable checkout of cirfig_gen. Its single-SVG workflow, consistent symbols,
orthogonal wires, layout JSON and slide-export approach were informed by
[Kwantae Kim's cirfig_gen](https://github.com/KwantaeKim/cirfig_gen), inspected at
commit `05cf185ed177ddab7a95ce37ad4366c668b3e7c3`.

The application does not execute upstream AGENTS.md instructions, the upstream
renderer or its font-generation tools. Symbol geometry/routing and application
adapters were recreated here with explicit canonical terminal maps, body/substrate
contacts and netlist-owned connections. Upstream path vertices are not treated
as arbitrary electrical pins. No upstream font files or glyph outlines are bundled.

Adapted design concepts retain the upstream MIT notice below. Original source
schematics in AnalogGenie remain original dataset assets and are not replaced by
generated drawings.

## Upstream MIT notice

MIT License

Copyright (c) 2026 Kwantae Kim

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
