# Demo assets

This folder hosts the demo recording referenced from the main README.

## Regenerate the cast / gif

Requires [vhs](https://github.com/charmbracelet/vhs) (a Charm tool that drives
a real terminal recording from a script).

```bash
vhs assets/demo.tape
```

Outputs:

- `assets/demo.cast` — asciinema cast file (the [README badge](../README.md)
  links to this when uploaded to [asciinema.org](https://asciinema.org))
- `assets/demo.gif` — preview animation, embedded inline in the README until
  the cast is uploaded

## Why no checked-in binary?

The CiteGuard repo deliberately keeps the recording artifacts small and
regeneratable.  The 30-second script in `demo.tape` is the source of truth;
the cast / gif are convenience artifacts.
