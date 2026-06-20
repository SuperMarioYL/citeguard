"""CiteGuard — batch-verify citations against real registries."""

from citeguard.models import Citation, NearestMatch, VerifyResult

__version__ = "0.4.0"
__all__ = ["Citation", "VerifyResult", "NearestMatch", "__version__"]
