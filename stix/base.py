# Copyright (c) 2015, The MITRE Corporation. All rights reserved.
# See LICENSE.txt for complete terms.

# stdlib
import json
import collections
import itertools
import StringIO

# mixbox
from mixbox import idgen
from mixbox import fields
from mixbox import binding_utils

from mixbox.cache import Cached
from mixbox.entities import Entity as _MixboxEntity
from mixbox.entities import EntityList as _MixboxEntityList

# internal
from . import utils

def _structured_text_list(input):
    from stix.common.structured_text import StructuredTextList

    if input:
        return StructuredTextList(input)
    else:
        return StructuredTextList()


def _override(*args, **kwargs):
    raise NotImplementedError()


class AttributeField(fields.TypedField):
    pass


class ElementField(fields.TypedField):
    pass


class ContentField(fields.TypedField):
    pass


class IdField(AttributeField):
    def __set__(self, instance, value):
        """Set the id field to `value`. If `value` is not None or an empty
        string, unset the idref fields on `instance`.
        """
        super(IdField, self).__set__(instance, value)

        if value:
            fields.unset(instance, IdrefField)



class IdrefField(AttributeField):
    def __set__(self, instance, value):
        """Set the idref field to `value`. If `value` is not None or an empty
        string, unset the id fields on `instance`.
        """
        super(IdrefField, self).__set__(instance, value)

        if value:
            fields.unset(instance, IdField)



class Entity(_MixboxEntity):
    """Base class for all classes in the STIX API."""
    _namespace = None
    _XSI_TYPE = None

    def _set_var(self, klass, try_cast=True, arg=None, **kwargs):
        """Sets an instance property value.

        * If the input value is ``None``, the property is set to ``None``.
        * If the input value is an instance of `klass`, the property is set
          the input value.
        * If the input value is not an instance of `klass` and `try_cast` is
          ``True``, an attempt will be made to cast the input value to an
          instance of `klass`.

        Args:
            klass: The expected input value class.
            try_cast: If ``True`` attempt to cast the input value to `klass`
                if it is not an instance of `klass`.
            arg: The __init__ parameter name to use when casting the input
                value to `klass`. E.g., StructuredText(value=input), the `arg`
                is `value`. If ``None``, it is assumed that the first
                __init__ parameter will accept the value.
            **kwargs: The field name and value. The field name is the key
                and the field value is the value.

        """
        name, item = next(kwargs.iteritems())
        attr = utils.private_name(name)  # 'title' => '_title'

        if item is None:
            setattr(self, attr, None)
        elif isinstance(item, klass):
            setattr(self, attr, item)
        elif try_cast:
            promoted = utils.cast_var(item, klass, arg=arg)
            setattr(self, attr, promoted)
        else:
            error = "'{0}' expects an instance of {1}. Received: {2}."
            error = error.format(name, klass, type(item))
            raise TypeError(error)

    def _set_vocab(self, klass=None, **kwargs):
        """Sets a controlled vocabulary property value.

        * If the input value is ``None``, the property is set to ``None``.
        * If the input value is an instance of ``VocabString``, the property
          is set to the input value.
        * If the input value is not an instance of ``VocabString``, an attempt
          will be made to cast the input to an instance of `klass`. If `klass`
          is ``None``, ``VocabString`` will be used.

        Args:
            klass: The VocabString impl to cast the input value to. If ``None``
                ``VocabString`` will be assumed.
            **kwargs: The field name, value pair. The field name is the key
                and the field value is the value.

        """
        from stix.common import VocabString

        klass = klass or VocabString
        item  = next(kwargs.itervalues())

        if isinstance(item, VocabString):
            self._set_var(VocabString, **kwargs)
        else:
            self._set_var(klass, **kwargs)

    def to_xml(self, include_namespaces=True, include_schemalocs=False,
               ns_dict=None, schemaloc_dict=None, pretty=True,
               auto_namespace=True, encoding='utf-8'):
        """Serializes a :class:`Entity` instance to an XML string.

        The default character encoding is ``utf-8`` and can be set via the
        `encoding` parameter. If `encoding` is ``None``, a unicode string
        is returned.

        Args:
            auto_namespace: Automatically discover and export XML namespaces
                for a STIX :class:`Entity` instance.
            include_namespaces: Export namespace definitions in the output
                XML. Default is ``True``.
            include_schemalocs: Export ``xsi:schemaLocation`` attribute
                in the output document. This will attempt to associate
                namespaces declared in the STIX document with schema locations.
                If a namespace cannot be resolved to a schemaLocation, a
                Python warning will be raised. Schemalocations will only be
                exported if `include_namespaces` is also ``True``.
            ns_dict: Dictionary of XML definitions (namespace is key, alias is
                value) to include in the exported document. This must be
                passed in if `auto_namespace` is ``False``.
            schemaloc_dict: Dictionary of XML ``namespace: schema location``
                mappings to include in the exported document. These will
                only be included if `auto_namespace` is ``False``.
            pretty: Pretty-print the XML.
            encoding: The output character encoding. Default is ``utf-8``. If
                `encoding` is set to ``None``, a unicode string is returned.

        Returns:
            An XML string for this
            :class:`Entity` instance. Default character encoding is ``utf-8``.

        """

        from .utils import nsparser
        parser = nsparser.NamespaceParser()

        if auto_namespace:
            ns_info = nsparser.NamespaceInfo()
        else:
            ns_info = None

        obj = self.to_obj(ns_info=ns_info)

        if (not auto_namespace) and (not ns_dict):
            raise Exception(
                "Auto-namespacing was disabled but ns_dict was empty "
                "or missing."
            )

        if auto_namespace:
            ns_info.finalize(ns_dict=ns_dict, schemaloc_dict=schemaloc_dict)
            obj_ns_dict = ns_info.binding_namespaces
        else:
            ns_info = nsparser.NamespaceInfo()
            ns_info.finalized_namespaces = ns_dict or {}
            ns_info.finalized_schemalocs = schemaloc_dict or {}
            obj_ns_dict = dict(
                itertools.chain(
                    ns_dict.iteritems(),
                    nsparser.DEFAULT_STIX_NAMESPACES.iteritems()
                )
            )

        namespace_def = ""
        if include_namespaces:
            xmlns = parser.get_xmlns_str(ns_info.finalized_namespaces)
            namespace_def += ("\n\t" + xmlns)

        if include_schemalocs and include_namespaces:
            schemaloc = parser.get_schemaloc_str(ns_info.finalized_schemalocs)
            namespace_def += ("\n\t" + schemaloc)

        if not pretty:
            namespace_def = namespace_def.replace('\n\t', ' ')

        with binding_utils.save_encoding(encoding):
            sio = StringIO.StringIO()
            obj.export(
                sio.write,                    # output buffer
                0,                            # output level
                obj_ns_dict,                  # namespace dictionary
                pretty_print=pretty,          # pretty printing
                namespacedef_=namespace_def   # namespace/schemaloc def string
            )

        # Ensure that the StringIO buffer is unicode
        s = unicode(sio.getvalue())

        if encoding:
            return s.encode(encoding)

        return s

    def walk(self):
        return utils.walk.iterwalk(self)

    def find(self, id_):
        """Searches the children of a :class:`Entity` implementation for an
        object with an ``id_`` property that matches `id_`.

        """
        if not id_:
            return

        for entity in self.walk():
            if id_ == getattr(entity, "id_", None):
                return entity


class EntityList(Entity, _MixboxEntityList):
    _contained_type = _override
    _inner_name = None
    _dict_as_list = False

    def to_list(self):
        return [h.to_dict() for h in self]

    def to_dict(self):
        if self._dict_as_list:
            return self.to_list()

        d = utils.to_dict(self, skip=('inner',))

        if self._inner:
            d[self._inner_name] = [h.to_dict() for h in self]

        return d

    @classmethod
    def from_obj(cls, obj, return_obj=None, contained_type=None,
                 binding_var=None):
        if not obj:
            return None

        if return_obj is None:
            return_obj = cls()
        if not contained_type:
            contained_type = cls._contained_type
        if not binding_var:
            binding_var = cls._binding_var

        for item in getattr(obj, binding_var):
            return_obj.append(contained_type.from_obj(item))

        return return_obj

    @classmethod
    def from_list(cls, list_repr, return_obj=None, contained_type=None):
        from stix.common.related import GenericRelationshipList

        if not utils.is_sequence(list_repr):
            return None

        if return_obj is None:
            return_obj = cls()
        if not contained_type:
            contained_type = cls._contained_type

        #print list_repr.__class__, isinstance(list_repr, GenericRelationshipList)

        # GenericRelationshipList is not actually a list; it's dict with a list member
        if issubclass(cls, GenericRelationshipList):
            return cls.from_dict(list_repr, return_obj)

        try:
            list_repr = list_repr[cls._inner_name]
        except:
            pass
        

        return_obj.extend(contained_type.from_dict(x) for x in list_repr)
        return return_obj

    @classmethod
    def from_dict(cls, dict_repr, return_obj=None, contained_type=None,
                  inner_name=None):

        if cls._dict_as_list:
            return cls.from_list(
                dict_repr,
                return_obj=return_obj,
                contained_type=contained_type,
            )

        if not isinstance(dict_repr, dict):
            return None

        if return_obj is None:
            return_obj = cls()
        if not contained_type:
            contained_type = cls._contained_type
        if not inner_name:
            inner_name = cls._inner_name

        if inner_name == "attribution":
            pass

        for item in dict_repr.get(inner_name, []):
            return_obj.append(contained_type.from_dict(item))

        return return_obj


class TypedCollection(object):
    """Abstract base class for non-STIX collections of entities.

    See also:
        TypedList

    """
    _contained_type = _override

    def __init__(self, *args):
        self._inner = []
        self._initialize_inner(*args)

    def _initialize_inner(self, *args):
        """Must be overridden by subclass.

        """
        raise NotImplementedError()

    def __len__(self):
        return len(self._inner)

    def __nonzero__(self):
        return bool(self._inner)

    def _is_valid(self, value):
        """Check if this is a valid object to add to the list."""
        # Subclasses can override this function, but if it becomes common,
        # it's probably better to use self._contained_type.istypeof(value)
        return isinstance(value, self._contained_type)

    def _fix_value(self, value):
        """Attempt to coerce value into the correct type.

        Subclasses can override this function.
        """
        try:
            new_value = self._contained_type(value)
        except Exception:
            error = "Can't put '{0}' ({1}) into a {2}. Expected a {3} object."
            error = error.format(
                value,                  # Input value
                type(value),            # Type of input value
                type(self),             # Type of collection
                self._contained_type    # Expected type of input value
            )
            raise ValueError(error)

        return new_value

    def to_obj(self, return_obj=None, ns_info=None):
        #print "TypedCollection to_obj called"
        return [x.to_obj(ns_info=ns_info) for x in self]

    def to_list(self):
        return [h.to_dict() for h in self]

    @classmethod
    def from_obj(cls, obj_list, contained_type=None):
        if not obj_list:
            return None

        if not contained_type:
            contained_type = cls._contained_type

        if not utils.is_sequence(obj_list):
            obj_list = [obj_list]

        items = (contained_type.from_obj(x) for x in obj_list)
        return cls(items)

    @classmethod
    def from_list(cls, list_repr, contained_type=None):

        if not list_repr:
            return cls()

        if isinstance(list_repr, dict) or not utils.is_sequence(list_repr):
            list_repr = [list_repr]

        if not contained_type:
            contained_type = cls._contained_type

        items = (contained_type.from_dict(x) for x in list_repr)
        return cls(items)

    from_dict = from_list
    to_dict = to_list

    @classmethod
    def object_from_dict(cls, entity_dict):
        """Convert from dict representation to object representation."""
        return cls.from_dict(entity_dict).to_obj()

    @classmethod
    def dict_from_object(cls, entity_obj):
        """Convert from object representation to dict representation."""
        return cls.from_obj(entity_obj).to_dict()
    
    @classmethod
    def istypeof(cls, obj):
        """Check if `cls` is the type of `obj`

        In the normal case, as implemented here, a simple isinstance check is
        used. However, there are more complex checks possible. For instance,
        EmailAddress.istypeof(obj) checks if obj is an Address object with
        a category of Address.CAT_EMAIL
        """
        return isinstance(obj, cls)


class TypedList(TypedCollection, collections.MutableSequence):
    def __init__(self, *args):
        TypedCollection.__init__(self, *args)

    def _initialize_inner(self, *args):
        # Check if it was initialized with args=None
        if not any(args):
            return

        for arg in args:
            if utils.is_sequence(arg):
                self.extend(arg)
            else:
                self.append(arg)

    def __getitem__(self, key):
        return self._inner.__getitem__(key)

    def __setitem__(self, key, value):
        if not self._is_valid(value):
            value = self._fix_value(value)
        self._inner.__setitem__(key, value)

    def __delitem__(self, key):
        self._inner.__delitem__(key)

    def __len__(self):
        return len(self._inner)

    def insert(self, idx, value):
        if not value:
            return
        if not self._is_valid(value):
            value = self._fix_value(value)
        self._inner.insert(idx, value)


class BaseCoreComponent(Cached, Entity):
    _ALL_VERSIONS = ()
    _ID_PREFIX = None

    title = ElementField("Title")
    id_ = IdField("id")
    idref = IdrefField("idref")
    version = AttributeField("version")
    timestamp = AttributeField("timestamp")
    handling = ElementField("Handling")

    # These are defined in init_typed_fields due to circular imports
    descriptions = None
    short_descriptions = None

    @classmethod
    def _init_typed_fields(cls):
        import data_marking
        import common
        from stix.common.structured_text import StructuredTextList, StructuredTextListField
        cls.handling.type_ = data_marking.Marking
        #cls.information_source.type_ = common.InformationSource
        cls.descriptions = StructuredTextListField("Description", StructuredTextList, key_name="description")
        cls.short_descriptions = StructuredTextListField("Short_Description", StructuredTextList, key_name="short_description")

    def __init__(self, id_=None, idref=None, timestamp=None, title=None,
                 description=None, short_description=None):
        
        super(BaseCoreComponent, self).__init__()
        
        self.id_ = id_ or idgen.create_id(self._ID_PREFIX)
        self.idref = idref
        self.title = title
        self.descriptions = _structured_text_list(description)
        self.short_descriptions = _structured_text_list(short_description)
        self.version = None
        #self.information_source = None
        self.handling = None

        if timestamp:
            self.timestamp = timestamp
        else:
            self.timestamp = utils.dates.now() if not idref else None


    # TODO: add this as a callback_hook to version TypedField
    def check_version(self, value):
        if not value:
            self._version = None
        else:
            utils.check_version(self._ALL_VERSIONS, value)
            self._version = value

    # 
    # @property
    # def timestamp(self):
    #     """The timestam property declares the time of creation and is
    #     automatically set in ``__init__()``.
    # 
    #     This property can accept ``datetime.datetime`` or ``str`` values.
    #     If an ``str`` value is supplied, a best-effort attempt is made to
    #     parse it into an instance of ``datetime.datetime``.
    # 
    #     Default Value: A ``datetime.dateime`` instance with a value of the
    #     date/time when ``__init__()`` was called.
    # 
    #     Note:
    #         If an ``idref`` is set during ``__init__()``, the value of
    #         ``timestamp`` will not automatically generated and instead default
    #         to the ``timestamp`` parameter, which has a default value of
    #         ``None``.
    # 
    #     Returns:
    #         An instance of ``datetime.datetime``.
    # 
    #     """
    #     return self._timestamp
    # 
    # @timestamp.setter
    # def timestamp(self, value):
    #     self._timestamp = utils.dates.parse_value(value)
    # 
    
    @property
    def description(self):
        """A single description about the contents or purpose of this object.

        Default Value: ``None``

        Note:
            If this object has more than one description set, this will return
            the description with the lowest ordinality value.

        Returns:
            An instance of :class:`.StructuredText`

        """
        return next(iter(self.descriptions), None)

    @description.setter
    def description(self, value):
        from stix.common.structured_text import StructuredTextList
        self.descriptions = StructuredTextList(value)

    def add_description(self, description):
        """Adds a description to the ``descriptions`` collection.

        This is the same as calling "foo.descriptions.add(bar)".

        """
        self.descriptions.add(description)

    @property
    def short_description(self):
        """A single short description about the contents or purpose of this
        object.

        Default Value: ``None``

        Note:
            If this object has more than one short description set, this will
            return the description with the lowest ordinality value.

        Returns:
            An instance of :class:`.StructuredText`

        """
        return next(iter(self.short_descriptions), None)

    @short_description.setter
    def short_description(self, value):
        from stix.common.structured_text import StructuredTextList
        self.short_descriptions = StructuredTextList(value)

    def add_short_description(self, description):
        """Adds a description to the ``short_descriptions`` collection.

        This is the same as calling "foo.short_descriptions.add(bar)".

        """
        self.short_descriptions.add(description)

    # 
    # @classmethod
    # def from_obj(cls, obj, return_obj=None):
    #     from stix.common import StructuredTextList, InformationSource
    #     from stix.data_marking import Marking
    # 
    #     if not return_obj:
    #         raise ValueError("Must provide a return_obj argument")
    # 
    #     if not obj:
    #         raise ValueError("Must provide an obj argument")
    # 
    #     return_obj.id_ = obj.id
    #     return_obj.idref = obj.idref
    #     return_obj.timestamp = obj.timestamp
    # 
    #     # These may not be found on the input obj if it isn't a full
    #     # type definition (e.g., used as a reference)
    #     return_obj.version = getattr(obj, 'version', None)
    #     return_obj.title = getattr(obj, 'Title', None)
    #     return_obj.descriptions = \
    #         StructuredTextList.from_obj(getattr(obj, 'Description', None))
    #     return_obj.short_descriptions = \
    #         StructuredTextList.from_obj(getattr(obj, 'Short_Description', None))
    #     return_obj.information_source = \
    #         InformationSource.from_obj(getattr(obj, 'Information_Source', None))
    #     return_obj.handling = \
    #         Marking.from_obj(getattr(obj, 'Handling', None))
    # 
    #     return return_obj
    # 
    # def to_obj(self, return_obj=None, ns_info=None):
    #     if not return_obj:
    #         raise ValueError("Must provide a return_obj argument")
    # 
    #     super(BaseCoreComponent, self).to_obj(
    #         return_obj=return_obj,
    #         ns_info=ns_info
    #     )
    # 
    #     return_obj.id = self.id_
    #     return_obj.idref = self.idref
    #     return_obj.version = self.version
    #     return_obj.Title = self.title
    # 
    #     if self.timestamp:
    #         return_obj.timestamp = utils.dates.serialize_value(self.timestamp)
    #     if self.descriptions:
    #         return_obj.Description = self.descriptions.to_obj(ns_info=ns_info)
    #     if self.short_descriptions:
    #         return_obj.Short_Description = self.short_descriptions.to_obj(ns_info=ns_info)
    #     if self.information_source:
    #         return_obj.Information_Source = self.information_source.to_obj(ns_info=ns_info)
    #     if self.handling:
    #         return_obj.Handling = self.handling.to_obj(ns_info=ns_info)
    # 
    #     return return_obj
    # 
    # @classmethod
    # def from_dict(cls, d, return_obj=None):
    #     from stix.common import StructuredTextList, InformationSource
    #     from stix.data_marking import Marking
    # 
    #     if not return_obj:
    #         raise ValueError("Must provide a return_obj argument")
    # 
    #     get = d.get
    #     return_obj.id_ = get('id')
    #     return_obj.idref = get('idref')
    #     return_obj.timestamp = get('timestamp')
    #     return_obj.version = get('version')
    #     return_obj.title = get('title')
    #     return_obj.descriptions = \
    #         StructuredTextList.from_dict(get('description'))
    #     return_obj.short_descriptions = \
    #         StructuredTextList.from_dict(get('short_description'))
    #     return_obj.information_source = \
    #         InformationSource.from_dict(get('information_source'))
    #     return_obj.handling = \
    #         Marking.from_dict(get('handling'))
    # 
    #     return return_obj
    # 
    # def to_dict(self):
    #     return super(BaseCoreComponent, self).to_dict()
    # 
    # 
