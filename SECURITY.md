# Security

tech2k-tools reads and writes the spreadsheets you select. It stores:

- Marcone credentials in a `.env` file in the user configuration directory
  (`~/Library/Application Support/tech2k-tools` on macOS,
  `~/.config/tech2k-tools` on Linux, `%APPDATA%\tech2k-tools` on Windows),
  created with mode 0600 where the platform supports it. Saving always writes
  there, never to the working directory. A `.env` in the current working
  directory and `MARCONE_*` environment variables are also read.
- A SQLite cache of looked-up part numbers and prices in the user cache
  directory (`~/Library/Caches/tech2k-tools` on macOS, `~/.cache/tech2k-tools`
  on Linux, `%LOCALAPPDATA%\tech2k-tools` on Windows). Demo mode uses a
  temporary database instead.

The only network host contacted is `my.marcone.com`, to sign in and look up
parts. There is no telemetry.

## Reporting a vulnerability

Please use
[GitHub's private vulnerability reporting](https://github.com/kjiwa/tech2k-tools/security/advisories/new)
rather than opening a public issue. If that option isn't available, email
kamil.jiwa@gmail.com.
