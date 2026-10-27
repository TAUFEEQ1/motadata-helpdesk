import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)

try:
    import jinja2

    _HAS_JINJA2 = True
except ImportError:  # pragma: no cover
    _HAS_JINJA2 = False


def render_helpdesk_template(template_content: str, variables: Dict[str, Any]) -> str:
    """Render a Motadata ServiceOps response template with provided variables.

    Converts help desk template syntax {#variable#} to Jinja2 syntax {{ variable }}
    and renders using Jinja2 if available, with a nested dictionary fallback.

    Args:
        template_content: Template string containing {#variable.path#} placeholders
        variables: Dictionary containing template context variables

    Returns:
        str: Rendered template text
    """
    if _HAS_JINJA2:
        try:

            def convert_to_jinja(match: re.Match) -> str:
                var_path = match.group(1).strip()
                return "{{ " + var_path + " }}"

            pattern = r"\{#([^#]+)#\}"
            jinja_template_content = re.sub(pattern, convert_to_jinja, template_content)

            env = jinja2.Environment(autoescape=False)
            template = env.from_string(jinja_template_content)
            return template.render(**variables)
        except Exception as e:
            logger.warning("Jinja2 rendering failed (%s); falling back to direct replacement", e)

    return _render_template_fallback(template_content, variables)


def _render_template_fallback(template_content: str, variables: Dict[str, Any]) -> str:
    """Fallback method using regex and nested key path resolution.

    Used when Jinja2 is unavailable or template compilation fails.
    """

    def replace_variable(match: re.Match) -> str:
        var_path = match.group(1).strip()
        try:
            val: Any = variables
            for key in var_path.split("."):
                val = val[key]
            return str(val)
        except (KeyError, TypeError, IndexError):
            logger.warning("Template variable '%s' not found in provided data", var_path)
            return match.group(0)

    pattern = r"\{#([^#]+)#\}"
    return re.sub(pattern, replace_variable, template_content)
