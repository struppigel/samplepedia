from django.apps import AppConfig


class SamplesConfig(AppConfig):
    name = 'samples'
    
    def ready(self):
        """Import signals when the app is ready."""
        import samples.signals
