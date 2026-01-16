# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-01-16

### Added

- Initial release
- ReverbClient for connecting to Laravel Reverb servers
- Support for public, private, and presence channels
- HMAC-SHA256 authentication for private/presence channels
- Automatic reconnection with exponential backoff
- Client events for bidirectional communication
- Configuration via environment variables and .env files
- Pydantic-based settings validation
- Comprehensive type hints
- Unit test suite
- GitHub Actions CI workflow
