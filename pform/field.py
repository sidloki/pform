import logging
from pyramid.compat import string_types
from player import render
from pform.interfaces import _, null, required
from pform.interfaces import Invalid, FORM_INPUT, FORM_DISPLAY

log = logging.getLogger('pform')


class Field(object):
    """Field base class.

    ``name``: Name of this field.

    ``title``: The title of this field.  Defaults to a titleization
      of the ``name`` (underscores replaced with empty strings and the
      first letter of every resulting word capitalized).  The title is
      used by form for generating html form.

    ``description``: The description for this field.  Defaults to
      ``''`` (the empty string).  The description is used by form.

    ``validator``: Optional validator for this field.  It should be
      an object that implements the
      :py:class:`pform.interfaces.Validator` interface.

    ``default``: Default field value.

    ``missing``: Field value if value is not specified in bound value.

    ``tmpl_widget``: The path to widget template.

    ``tmpl_input``: The path to input widget template. It should be
      compatible with pyramid renderers.

    ``tmpl_display``: The path to display widget template. It should be
      compatible with pyramid renderers.

    """

    __field__ = ''

    name = ''
    title = ''
    description = ''
    required = False
    error = None

    request = None
    params = {}
    mode = None
    value = null
    form_value = None
    context = None

    id = None
    klass = None
    typ = None

    tmpl_widget = None
    tmpl_input = None
    tmpl_display = None

    def __init__(self, name, **kw):
        self.__dict__.update(kw)

        self.name = name
        self.title = kw.get('title', name.capitalize())
        self.description = kw.get('description', '')
        self.readonly = kw.get('readonly', None)
        self.default = kw.get('default', null)
        self.missing = kw.get('missing', required)
        self.preparer = kw.get('preparer', None)
        self.validator = kw.get('validator', None)
        self.required = self.missing is required

    def bind(self, request, prefix, value, params, context=None):
        """ Bind field to value and request params """
        clone = self.__class__.__new__(self.__class__)
        clone.__dict__.update(self.__dict__)
        clone.request = request
        clone.value = value
        clone.params = params
        clone.name = '%s%s' % (prefix, self.name)
        clone.id = clone.name.replace('.', '-')
        clone.context = context
        return clone

    def update(self):
        """ Update field, prepare field for rendering """
        if self.mode is None:
            if self.readonly:
                self.mode = FORM_DISPLAY
            else:
                self.mode = FORM_INPUT

        # extract from request
        widget_value = self.extract()
        if widget_value is not null:
            self.form_value = widget_value
            return

        value = null

        # get from value
        if self.value is not null:
            value = self.value

        # use default
        if value is null:
            value = self.default

        # Convert the value to one that the widget can understand
        if value is not null:
            try:
                value = self.to_form(value)
            except Invalid as err:
                value = null
                log.error("%s", err)

            self.form_value = value if value is not null else None

    def to_form(self, value):
        """ return value representation siutable for html widget """
        return value

    def to_field(self, value):
        """ convert form value to field value """
        return value

    def validate(self, value):
        """ validate value """
        if self.typ is not None and not isinstance(value, self.typ):
            raise Invalid(self, _('Wrong type'))

        if value is required:
            raise Invalid(self, _('Required'))

        if self.validator is not None:
            self.validator(self, value)

    def extract(self, default=null):
        """ extract value from params """
        value = self.params.get(self.name, default)
        if value is default or not value:
            return default
        return value

    def render(self):
        """ render field """
        if self.mode == FORM_DISPLAY:
            tmpl = self.tmpl_display
        else:
            tmpl = self.tmpl_input

        if isinstance(tmpl, string_types):
            return render(self.request, tmpl, self, view=self)
        else:
            return tmpl(view=self, context=self, request=self.request)

    def render_widget(self):
        """ render field widget """
        tmpl = self.tmpl_widget or 'fields:widget'
        return render(self.request, tmpl, self, view=self)

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, self.name)


class FieldFactory(Field):
    """ Create field by name. First argument name of field registered
    with :py:func:`pform.field` decorator.

    Example:

    .. code-block:: python

       @form.field('customfield')
       class CustomField(form.Field):
           ...

       # Now `customfield` can be used for generating field:

       field = form.FieldFactory(
           'customfield', 'fieldname', ...)

    """

    __field__ = ''

    def __init__(self, typ, name, **kw):
        self.__field__ = typ

        super(FieldFactory, self).__init__(name, **kw)

    def bind(self, request, prefix, value, params, context=None):
        try:
            cls = request.registry['pform:field'][self.__field__]
        except KeyError:
            cls = None

        if cls is None:
            raise TypeError(
                "Can't find field implementation for '%s'" % self.__field__)

        clone = cls.__new__(cls)
        clone.__dict__.update(self.__dict__)
        clone.request = request
        clone.value = value
        clone.params = params
        clone.name = '%s%s' % (prefix, self.name)
        clone.id = clone.name.replace('.', '-')
        clone.context = context
        return clone