"""PredigtUploader package."""

from importlib.metadata import PackageNotFoundError, version


try:
    __version__ = version("predigt-uploader")
except PackageNotFoundError:
    __version__ = "unknown"
