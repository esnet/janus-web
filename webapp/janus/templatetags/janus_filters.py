from django import template
from django.template.defaulttags import register

register = template.Library()

@register.filter
def get_form(dictionary, key):
    return dictionary.get(key)

@register.filter
def get_type(value):
    return type(value).__name__
