# Security policy

## Supported versions

Security fixes go into the newest release. Please update before reporting, and
check whether the problem is still there.

| Version | Supported |
| --- | --- |
| Latest release | Yes |
| Anything older | No |

## Reporting a vulnerability

**Do not open a public issue for a security problem.** Use GitHub's private
reporting instead: on the repository's **Security** tab, choose **Report a
vulnerability**. Include what you found, the steps to reproduce it, the version and
platform, and what an attacker could do with it.

You can expect an acknowledgement within a week. We will keep you informed while it
is fixed and credit you in the release notes, unless you would rather not be named.

## What counts

formcut runs on your own machine, so the things that matter most are the ways
something outside it could get in:

- **The engine** binds to loopback (127.0.0.1). Anything that makes it reachable
  from another machine without the person turning that on.
- **The network listener** for phones and other computers (off by default, port
  8977): getting past the one-time pairing code, reusing or forging a device token,
  or reaching anything it should not expose.
- **The window key**: formcut's window holds a key made at each launch, and every
  change a program on the same computer makes to a project or a setting needs it.
  Anything that lets a program other than the window make a change without it, or
  that hands the key to one.
- **Outside agents**: a program that is not the formcut window must be asked about
  in the window before it changes anything (Ask each time, Allowed or Blocked in
  Settings, Connections, Outside agents). Anything that skips the question, lets
  an agent change that choice, or forges the sealed copy of it.
- **Provider keys and tokens** kept by the engine: anything that leaks them.
- **Files**: importing, downloading or extracting media or archives in a way that
  writes outside where it should.
- **formcut's ffmpeg**: anything that gets a download past the check of every file
  against the record formcut carries.
- **Webhooks**: forging or replaying a signed export notification.

Bugs that need someone to already control your machine, or to run a modified build
of formcut, are ordinary bugs: please open an issue for those.
