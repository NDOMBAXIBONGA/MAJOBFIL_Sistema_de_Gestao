from django import template

register = template.Library()

@register.filter
def get_attribute(obj, attr):
    """Obtém o valor de um atributo de um objeto dinamicamente"""
    try:
        return getattr(obj, attr, '')
    except (AttributeError, ValueError):
        return ''