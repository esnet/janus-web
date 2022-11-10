from django import template
from django.template.defaulttags import register

register = template.Library()

@register.filter
def get_form(dictionary, key):
    return dictionary.get(key)
