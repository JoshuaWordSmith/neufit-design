#!/usr/bin/env python3
# coding=utf-8

# MIT License
#
# Copyright 2017 Niels Lohmann <http://nlohmann.me>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS
# OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT
# OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import json
import sys
import os
from typing import List, Optional, Any, Set


def resolve_ref(ref):
    return ref.split('/')[-1]

def get_component(whole, content, key) -> tuple:
    item: dict = content.get(key, {})
    schema: dict = item.get('schema', {})
    ref: str = schema.get('$ref', '')

    if (ref):
        ref_name: str = resolve_ref(ref)
        schemas: dict = whole.get('components').get('schemas', {})
        return schemas.get(ref_name, {}), ref_name
    
    return {}, ref


def params_from_body(whole, request_body):
    """
    requestBody:
        description: user information to update
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UpdateUserRequest'
    """

    """
    UpdateMeetingRequest:
      type: object
      properties:
        startTime:
          type: string
          description: stringified timestamp of when to start the meeting
          enum: ["06-06-2020 12:00:00 UTC"]
          example: "06-06-2020 12:00:00 UTC"
        endTime:
          type: string
          description: stringified timestamp of when to end the meeting
          enum: ["06-06-2020 13:00:00 UTC"]
          example: "06-06-2020 13:00:00 UTC"
        users:
          type: array
          description: the users currently in the meeting
          items:
            type: string
            description: a user id
            example: instructorId_5
          example:
            - instructorId_5
            - customerId_1
            - customerId_5
            - customerId_3
    """
    content: dict = request_body.get('content', {})
    if (not content):
        return []

    result: list = []
    description: str = request_body.get('description', '')

    for key in content:
        ref, ref_name = get_component(whole, content, key)

        if (ref):
            properties: list = ref.get('properties', [])

            for prop in properties:
                item = properties.get(prop, {})
                item_description = item.get('description', description)
                required = item.get('required', False)

                result.append({
                    'in': 'body',
                    'name': f'{prop} - {ref_name}',
                    'description': item_description,
                    'required': required,
                    'schema': item,
                    'status': ref_name
                })

    return result

def expand_content(status: str, response: dict, response_collection: list, whole):
    content: dict = response.get('content', {'application/json': {}})
    description: str = response.get('description', '')

    for key in content:
        item: dict = content.get(key, {})
        schema: dict = item.get('schema', {})
        ref: str = schema.get('$ref', '')

        if (ref):
            ref_name: str = resolve_ref(ref)
            schemas: dict = whole.get('components').get('schemas', {})
            response_obj: dict = schemas.get(ref_name, {})

            response_collection.append((status, {
                'description':description,
                key: response_obj,
                '$ref': ref,
                # 'type': key
            }))
        else:
            response_collection.append((status, {
                'description':description,
                key: item,
                'type': key
            }))

def expand_responses(whole, d, responses) -> list:
    response_collection: list = []

    for status, response in responses:
        if ('content' in response):
            expand_content(status, response, response_collection, whole)
        else:
            response_collection.append((status, response))

    return response_collection

class Property:
    def __init__(self, name, type, required, example=None, description=None, default=None, enum=None, format=None,
                 items=None, maximum=None, exclusive_maximum=False, minimum=None, exclusive_minimum=False,
                 multiple_of=None, max_length=None, min_length=0, pattern=None, max_items=None, min_items=0,
                 unique_items=False, ref_type=None):
        # type
        self.type = type  # type: str
        self.format = format  # type: Optional[str]
        self.ref_type = ref_type  # type: Optional[str]

        # constraints
        self.required = required  # type: bool
        self.enum = enum  # type: Optional[List[Any]]

        # documentation
        self.name = name  # type: str
        self.example = example  # type: Optional[Any]
        self.description = description  # type: Optional[str]
        self.default = default  # type: Optional[Any]

        # numbers
        self.maximum = maximum  # type: Optional[float,int]
        self.exclusive_maximum = exclusive_maximum  # type: bool
        self.minimum = minimum  # type: Optional[float,int]
        self.exclusive_minimum = exclusive_minimum  # type: bool
        self.multiple_of = multiple_of  # type: Optional[float,int]

        # strings
        self.max_length = max_length  # type: Optional[int]
        self.min_length = min_length  # type: int
        self.pattern = pattern  # type: Optional[str]

        # arrays
        self.max_items = max_items  # type: Optional[int]
        self.min_items = min_items  # type: int
        self.unique_items = unique_items  # type: bool
        self.items = items  # type: Optional[str]

    @staticmethod
    def from_dict(property_name, d, required):
        # whether the type was resolved
        ref_type = None
        type_str = '<i>Not Specified</i>'

        # We use the Parameter class for parameters inside the swagger specification, but also for parameters. There,
        # type information is given in a "schema" property.
        if 'type' in d or '$ref' in d:
            type_dict = d
        elif 'schema' in d:
            type_dict = d['schema']
        elif 'allOf' in d and len(d['allOf']) > 0:
            type_dict = d['allOf'][0]
        else:
            type_dict = {}

        # type is given or must be resolved from $ref
        if '$ref' in type_dict:
            type_str = resolve_ref(type_dict['$ref'])
            ref_type = type_str

        if 'type' in type_dict:
            type_str = type_dict['type']


        # join multiple types to string
        if isinstance(type_str, list):
            type_str = '/'.join(type_str)

        # items type is given or must be resolved from $ref
        if 'items' in type_dict:
            if 'type' in type_dict['items']:
                items = type_dict['items']['type']
            else:
                items = resolve_ref(type_dict['items']['$ref'])
                ref_type = items
        else:
            items = None

        return Property(
            name=property_name,
            type=type_str,
            required=required,
            example=d.get('example'),
            description=d.get('description'),
            default=d.get('default'),
            enum=d.get('enum'),
            format=d.get('format'),
            items=items,
            maximum=d.get('maximum'),
            exclusive_maximum=d.get('exclusiveMaximum', False),
            minimum=d.get('minimum'),
            exclusive_minimum=d.get('exclusiveMinimum', False),
            multiple_of=d.get('multipleOf'),
            max_length=d.get('maxLength'),
            min_length=d.get('minLength', 0),
            pattern=d.get('pattern'),
            max_items=d.get('maxItems', 0),
            min_items=d.get('minItems'),
            unique_items=d.get('uniqueItems', False),
            ref_type=ref_type
        )

    @property
    def uml(self):
        # type or array
        if self.type == 'array':
            # determine lower and upper bound
            lower = ''
            upper = ''
            if self.min_items:
                lower = self.min_items if not self.exclusive_minimum else self.min_items + 1
            if self.max_items:
                upper = self.max_items if not self.exclusive_minimum else self.max_items - 1

            # combine lower and upper bound to bounds string
            bounds = ''
            if lower or upper:
                bounds = '{lower}:{upper}'.format(lower=lower, upper=upper)

            type_str = '{items}[{bounds}]'.format(items=self.items, bounds=bounds)
        else:
            type_str = self.type

        # format (e.g., date-time)
        if self.format:
            type_str += ' ({format})'.format(format=self.format)

        # name string (bold if property is required)
        if self.required:
            name_str = '<b>{name}</b>'.format(name=self.name)
        else:
            name_str = self.name

        # simple type definition ({field} is a keyword for PlantUML)
        result = '{{field}} {type_str} {name_str}'.format(type_str=type_str, name_str=name_str)

        # enum
        if self.enum is not None:
            result += ' {{{enum_str}}}'.format(enum_str=', '.join([json.dumps(x) for x in self.enum]))

        # min/max
        if self.minimum or self.maximum:
            minimum = self.minimum if self.minimum is not None else ''
            maximum = self.maximum if self.maximum is not None else ''
            result += ' {{{minimum}..{maximum}}}'.format(minimum=minimum, maximum=maximum)

        # default value
        if self.default is not None:
            result += ' = {default}'.format(default=json.dumps(self.default))

        return result


class Definition:
    def __init__(self, name, type, properties, relationships):
        self.name = name  # type: str
        self.type = type  # type: str
        self.properties = properties  # type: List[Property]
        self.relationships = relationships  # type: Set[str]

    @staticmethod
    def from_dict(name, d):
        properties = []  # type: List[Property]
        for property_name, property in d.get('properties', {}).items():
            properties.append(Property.from_dict(
                property_name=property_name,
                d=property,
                required=property_name in d.get('required', [])
            ))

        if not 'type' in d:
            print('required key "type" not found in dictionary ' + json.dumps(d), file=sys.stderr)

        return Definition(name=name,
                          type=d['type'],
                          properties=properties,
                          relationships={property.ref_type for property in properties if property.ref_type})

    @property
    def uml(self):
        result = 'class {name} {{\n'.format(name=self.name)

        # required properties first
        for property in sorted(self.properties, key=lambda x: x.required, reverse=True):
            result += '    {property_str}\n'.format(property_str=property.uml)

        result += '}\n\n'

        # add relationships
        for relationship in sorted(self.relationships):
            result += '{name} ..> {relationship}\n'.format(name=self.name, relationship=relationship)

        return result


class Parameter:
    def __init__(self, name, location, description, required, property):
        self.name = name  # type: str
        self.location = location  # type: str
        self.description = description  # type: Optional[str]
        self.required = required  # type: bool
        self.property = property  # type: Property

    @staticmethod
    def from_dict(whole, d):
        ref = d.get('$ref')
        if ref != None:
            d = whole['parameters'][resolve_ref(ref)]
        return Parameter(
            name=d['name'],
            location=d['in'],
            description=d.get('description'),
            required=d.get('required', False),
            property=Property.from_dict(d['name'], d, d.get('required', False))
        )


class Response:
    def __init__(self, status, description, property):
        self.status = status  # type: str
        self.description = description  # type: Optional[str]
        self.property = property  # type: Property

    @staticmethod
    def from_dict(whole, status, d):
        return Response(
            status=status,
            description=d.get('description'),
            property=Property.from_dict('', d, False)
        )

    @property
    def uml(self):
        return '{status}: {type}'.format(
            status=self.status,
            type=self.property.uml
        )


class Operation:
    def __init__(self, path, type, summary, description, responses, tags, parameters):
        self.path = path  # type: str
        self.type = type  # type: str
        self.summary = summary  # type: Optional[str]
        self.description = description  # type: Optional[str]
        self.responses = responses  # type: List[Response]
        self.tags = tags  # type: List[str]
        self.parameters = parameters  # type: List[Parameter]

    def __lt__(self, other):
        return self.type < other.type

    @staticmethod
    def build_responses(whole, d):
        responses: list = d['responses'].items()
        has_content_block: bool = any(['content' in response for status, response in responses])
        if (has_content_block):
            responses = expand_responses(whole, d, responses)

        return [Response.from_dict(whole, status, response) for status, response in responses]

    @staticmethod
    def from_dict(whole, path, type, d, path_parameters):
        summary = d.get('summary')
        description = d.get('description')
        tags = d.get('tags')
        request_body = d.get('requestBody', {})


        responses = Operation.build_responses(whole, d)

        params = d.get('parameters', [])
        body_params = params_from_body(whole, request_body)
        params = params + body_params

        parameters = [Parameter.from_dict(whole, param) for param in params]
        parameters = path_parameters + parameters

        return Operation(
            path=path,
            type=type,
            summary=summary,
            description=description,
            tags=tags,
            responses=responses,
            parameters=parameters
        )

    @property
    def uml(self):
        # collect used parameter locations
        possible_types = ['header', 'path', 'query', 'cookie', 'body']
        parameter_types = {x.location for x in self.parameters}

        parameter_strings = []
        for parameter_type in [x for x in possible_types if x in parameter_types]:
            # add heading
            parameter_strings.append('.. {parameter_type} ..'.format(parameter_type=parameter_type))
            # add parameters
            for parameter in [x for x in self.parameters if x.location == parameter_type]:
                parameter_strings.append('{parameter_uml}'.format(parameter_uml=parameter.property.uml))

        # collect references from responses and parameters
        references = [x.property.ref_type for x in self.responses if x.property.ref_type] + \
                     [x.property.ref_type for x in self.parameters if x.property.ref_type]

        return """class "{name}" {{\n{parameter_str}\n.. responses ..\n{response_str}\n}}\n\n{associations}\n""".format(
            name=self.name,
            response_str='\n'.join([x.uml for x in self.responses]),
            parameter_str='\n'.join(parameter_strings),
            associations='\n'.join({'"{name}" ..> {type}'.format(name=self.name, type=type) for type in references})
        )

    @property
    def name(self):
        return '{type} {path}'.format(
            type=self.type.upper(),
            path=self.path
        )


class Path:
    def __init__(self, path, operations):
        self.path = path  # type: str
        self.operations = operations  # type: List[Operation]

    @staticmethod
    def from_dict(whole, path_name, d):

        params: list  = d.get('parameters', [])
        parameters = [Parameter.from_dict(whole, p) for p in params]

        ignore: set = {'parameters', 'summary', 'description'}
        items: list = [(t, op) for t, op in d.items() if t not in ignore]
        operations: list = [Operation.from_dict(whole, path_name, t, op, parameters) for t, op in items]

        return Path(
            path=path_name,
            operations=operations
        )

    @property
    def uml(self):
        return 'interface "{path}" {{\n}}\n\n{operation_str}\n{association_str}\n\n'.format(
            path=self.path,
            operation_str='\n'.join([op.uml for op in self.operations]),
            association_str='\n'.join(['"{path}" ..> "{operation_name}"'.format(
                path=self.path, operation_name=op.name) for op in sorted(self.operations)])
        )


class Swagger:
    def __init__(self, definitions, paths):
        self.definitions = definitions  # type: List[Definition]
        self.paths = paths  # type: List[Path]

    @staticmethod
    def from_dict(d):
        definitions = [Definition.from_dict(name, definition) for name, definition in d.get('components',{}).get('schemas', {}).items()]
        paths = [Path.from_dict(d, path_name, path) for path_name, path in d['paths'].items()]
        return Swagger(definitions=definitions, paths=paths)

    @staticmethod
    def from_file(filename):
        loader = json.load
        if filename.endswith('.yml') or filename.endswith('.yaml'):
            import yaml
            loader = yaml.load
        with open(filename, 'r') as fd:
            return Swagger.from_dict(loader(fd))

    @property
    def uml(self):
        uml_str = '@startuml\nhide empty members\nset namespaceSeparator none\n\n{paths}\n{definitions}\n@enduml\n'
        return uml_str.format(
            paths='\n\n'.join([d.uml for d in self.paths]),
            definitions='\n\n'.join([d.uml for d in self.definitions])
        )


if __name__ == '__main__':
    input_file_name = 'docs/swagger.yaml'
    output_file_name = 'docs/swagger.puml'

    if (len(sys.argv) > 1):
        input_file_name = sys.argv[1]

    if (len(sys.argv) > 2):
        output_file_name = sys.argv[2]

    sw = Swagger.from_file(input_file_name)

    with open(output_file_name, 'w') as file:
        file.write(sw.uml)

    os.system(f'plantuml {output_file_name} -tpng')
