from .models import SiteConfig


def site_config(request):
    """Inject the singleton SiteConfig into every template context."""
    return {'site_config': SiteConfig.get()}
