from . import __version__
from .models import SiteConfig


def site_config(request):
    """Inject SiteConfig and app version into every template context."""
    return {'site_config': SiteConfig.get(), 'app_version': __version__}
