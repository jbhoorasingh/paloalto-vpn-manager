from auditlog.registry import auditlog
from django.conf import settings
from django.db import models

# The default global template reproduces the generator's output verbatim:
# every computed section's commands one per line, sections separated by a
# blank line. Engineers can reorder, filter, or extend from here using the
# documented context variables.
DEFAULT_CONFIG_TEMPLATE = """\
{% for section in sections %}
{% for cmd in section.commands %}
{{ cmd }}
{% endfor %}
{% if not loop.last %}

{% endif %}
{% endfor %}
"""

GLOBAL_TEMPLATE_NAME = "global"


class ConfigTemplate(models.Model):
    """
    The Jinja template that renders a request's per-site PAN-OS configuration.

    One row (name='global') is the platform-wide template; individual requests
    can carry their own override (VpnRequest.config_template_override). Both
    are audit-logged.
    """

    name = models.CharField(max_length=50, unique=True, default=GLOBAL_TEMPLATE_NAME)
    content = models.TextField(default=DEFAULT_CONFIG_TEMPLATE)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="config_templates_updated",
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"Config template '{self.name}'"

    @property
    def is_default(self):
        return self.content == DEFAULT_CONFIG_TEMPLATE

    @classmethod
    def get_global(cls):
        template, _ = cls.objects.get_or_create(
            name=GLOBAL_TEMPLATE_NAME,
            defaults={"content": DEFAULT_CONFIG_TEMPLATE},
        )
        return template


auditlog.register(
    ConfigTemplate,
    exclude_fields=["id", "created_at", "updated_at"],
)
