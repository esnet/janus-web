from django import template
from django.template.defaulttags import register

register = template.Library()

@register.filter
def get_form(dictionary, key):
    return dictionary.get(key)

@register.filter
def get_type(value):
    return type(value).__name__

@register.filter
def get_key(value, arg):
    return value.get(arg, None)

@register.filter
def addstr(arg1, arg2):
    return str(arg1) + str(arg2)
