# Contributing to MozJPEG Compressor

Thank you for your interest in contributing to MozJPEG Compressor! We welcome contributions from the community, whether they're bug reports, feature requests, documentation improvements, or code contributions.

## Code of Conduct

Please be respectful and constructive in all interactions. We aim to foster a welcoming and inclusive environment for all contributors.

## How to Contribute

### Reporting Bugs

If you find a bug, please open an **Issue** with:

1. **Clear title** - e.g., "Crash when compressing PNG files"
2. **Detailed description** - What happened? What did you expect to happen?
3. **Steps to reproduce** - Exact steps to trigger the bug
4. **Environment** - Windows version, Python version, MozJPEG version
5. **Error message** - Full error traceback (if available)
6. **Screenshot** - Visual evidence (if applicable)

### Requesting Features

For feature requests, open an **Issue** with:

1. **Clear title** - e.g., "Add support for WebP format"
2. **Why you need it** - Use case and business value
3. **Proposed solution** - How should it work?
4. **Alternatives considered** - Other ways to solve this?

### Submitting Code Changes

#### 1. Fork the repository

```bash
# On GitHub, click "Fork" button
```

#### 2. Clone your fork

```bash
git clone https://github.com/YOUR_USERNAME/fgphoto-mozjpeg-compressor.git
cd fgphoto-mozjpeg-compressor
```

#### 3. Create a feature branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix-name
```

Branch naming convention:
- `feature/` — New features
- `fix/` — Bug fixes
- `docs/` — Documentation updates
- `refactor/` — Code restructuring (no functionality change)
- `chore/` — Maintenance tasks

#### 4. Make your changes

- Keep changes focused and atomic
- Follow the existing code style
- Add comments for non-obvious logic
- Update docstrings where applicable
- Test your changes locally

#### 5. Commit with clear messages

```bash
git commit -m "brief description

Optional longer explanation of what changed and why."
```

Commit message format:
- Use imperative mood ("Add feature" not "Added feature")
- Keep first line under 50 characters
- Reference related issues: "Fixes #123"

#### 6. Push to your fork

```bash
git push origin feature/your-feature-name
```

#### 7. Open a Pull Request

On GitHub:
1. Compare your branch to `master`
2. Fill in the PR description:
   - What problem does this solve?
   - How can it be tested?
   - Any breaking changes?
   - Related issues (e.g., "Fixes #123")

#### 8. Address review feedback

- Respond to comments
- Make requested changes
- Push additional commits (don't force-push unless asked)
- Ping reviewers after updates

#### 9. Merge

Once approved, your PR will be merged into `master` and released in the next version.

## Development Setup

### Prerequisites

- Python 3.8+
- Git

### Installation

```bash
# Clone the repo
git clone https://github.com/filipecosgom/fgphoto-mozjpeg-compressor.git
cd fgphoto-mozjpeg-compressor

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

### Running Locally

```bash
python main.py
```

### Code Style

- Follow PEP 8 (Python style guide)
- Use meaningful variable names
- Keep functions focused and small
- Add type hints where possible
- Write docstrings for classes and public methods

### Testing

Before submitting a PR, test:
- [ ] Application starts without errors
- [ ] File browsing works
- [ ] Compression completes successfully
- [ ] Preview displays correctly
- [ ] No crashes with edge cases

## Documentation

Help improve the docs:

- **README.md** - Project overview and usage guide
- **CONTRIBUTING.md** - This file
- **CHANGELOG.md** - Release notes and version history
- **Code comments** - Inline explanations of complex logic
- **Docstrings** - Function and class documentation

## Questions?

- Open a GitHub **Issue** for questions
- Check existing issues/PRs before asking
- Be specific and provide context
- Include relevant details (version, OS, steps taken)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Happy contributing! 🚀**
