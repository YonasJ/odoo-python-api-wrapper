import os
from odoo_api_wrapper import OdooBackend,OdooTransaction


class Klass:
    model_classes = {}
    def __init__(self, odoo:OdooTransaction, model, name):
        self.name = name
        self.model = model
        self.model_classes[model] = self.name
        self.imports = {}
        self.add_import("db.OdooDataClass", "OdooDataClass")
        self.add_import("odoo_base", "OdooTransaction")
        # self.add_import("odoo_base", "ObjectWrapper")
        self.add_import("typing", "TypeVar")
        self.type_only_forward_imports = {}
        self.odoo: OdooTransaction = odoo

    def add_import(self,ifrom:str,iitem:str) -> str:
        if ifrom in self.imports:
            if not iitem in self.imports[ifrom]:
                self.imports[ifrom] = ",".join([self.imports[ifrom], iitem])
        else:
            self.imports[ifrom] = iitem
        return iitem

    def field(self, field,read_only) -> None:
        prop_name = field_name = field['name']

        db_type = field['ttype']

        
        if field_name.startswith("x_"):
            prop_name = field_name.replace("x_", "", 1)

        self.fields += f"    _{prop_name.upper()} = '{field_name}'\n"

        if db_type == 'many2one':
            assert prop_name.endswith("_id"), "expected many2one to end in _id"
            rel_prop_name = prop_name[:-3]
            other_class_name = self.model_classes[field['relation']]
            self.type_only_forward_imports[f"db.{other_class_name}"] = other_class_name
            self.fields += f"    @property\n"
            self.fields += f"    def {rel_prop_name}(self) -> {other_class_name}:\n"
            self.fields += f"        from db.{other_class_name} import {other_class_name}\n"
            self.fields += f"        return self.get_many2one(self._{prop_name.upper()}, {other_class_name}) # type: ignore\n"

            self.fields += f"    @{rel_prop_name}.setter\n"
            self.fields += f"    def {rel_prop_name}(self, value:{other_class_name}) -> None:\n"
            self.fields += f"        self.set_many2one(self._{prop_name.upper()}, value)\n"

            py_type = "int"
            self.fields += f"    def get_{prop_name}(self, when_none:T=None) -> {py_type}|T:\n"
            self.fields += f"        ret:OdooDataClass = self.get_data(self._{prop_name.upper()}) # type: ignore\n"
            
            self.fields += f"        if ret:\n"
            self.fields += f"            ret2 =ret.id\n"
            self.fields += f"            if ret2:\n"
            self.fields += f"                return ret2\n"
            self.fields += f"        return when_none\n"

            self.fields += f"    @property\n"
            self.fields += f"    def {prop_name}(self) -> {py_type}:\n"
            self.fields += f"        ret = self.get_{prop_name}()\n"
            self.fields += f"        if ret is None: raise ValueError(f'Key {prop_name} is not set.')\n"
            self.fields += f"        return ret\n\n"            
        elif db_type == 'one2many':
            # self.imports['typing'] = 'list'
            other_class_name = self.model_classes[field['relation']]
            self.type_only_forward_imports[f"db.{other_class_name}"] = other_class_name
            self.fields += f"    @property\n"
            self.fields += f"    def {prop_name}(self) -> list[{other_class_name}]:\n"
            self.fields += f"        from db.{other_class_name} import {other_class_name}\n"
            self.fields += f"        return self.get_one2many(self._{prop_name.upper()}, {other_class_name}, '{field['relation_field']}') # type: ignore\n"

            # self.fields += f"    @{prop_name}.setter\n"
            # self.fields += f"    def {prop_name}(self, value:{other_class_name}) -> None:\n"
            # self.fields += f"        self.set_one2many(self._{prop_name.upper()}, value)\n"
            # self.fields += f"\n"
        else:                    
            
            match db_type:
                case 'float': py_type = py_conversion = 'float'
                case 'date': 
                    py_type = self.add_import("datetime", "datetime")
                    py_conversion = 'date'
                    
                case 'datetime':  
                    py_type = self.add_import("datetime", "datetime")
                    py_conversion = 'date'
                case 'many2one':
                    py_conversion = 'int'
                    py_type = 'int'
                case 'integer':  py_type = py_conversion = 'int'
                case 'boolean':  py_type = py_conversion = 'bool'
                case 'char':  py_type = py_conversion = 'str'
                case _:  # Default case
                    py_type = py_conversion = 'str'
                
            if py_conversion == 'date':
                self.fields += f"    def get_{prop_name}_str(self, format:str = '%Y-%m-%d', when_none:T=None) -> str|T:\n"
                self.fields += f"        ret = self.get_data_{py_conversion}(self._{prop_name.upper()})\n"
                self.fields += f"        if ret is None: \n"
                self.fields += f"            return when_none\n"
                self.fields += f"        return ret.strftime(format)\n"
                
            self.fields += f"    def get_{prop_name}(self, when_none:T=None) -> {py_type}|T:\n"
            self.fields += f"        ret = self.get_data_{py_conversion}(self._{prop_name.upper()})\n"
            self.fields += f"        if ret is None: \n"
            self.fields += f"            return when_none\n"
            self.fields += f"        return ret\n"


            self.fields += f"    @property\n"
            self.fields += f"    def {prop_name}(self) -> {py_type}:\n"
            self.fields += f"        ret = self.get_{prop_name}()\n"
            self.fields += f"        if ret is None: raise ValueError(f'Key {prop_name} is not set.')\n"
            self.fields += f"        return ret\n"
                
            if not read_only:            
                self.fields += f"    @{prop_name}.setter\n"
                self.fields += f"    def {prop_name}(self, value:{py_type}|None) -> None:\n"
                self.fields += f"        self.set_data_{py_conversion}(self._{prop_name.upper()}, value)\n"
                            
            self.fields += "\n\n"

    def save(self):
        
        
        self.file_name_base = f'db/{self.name}B.py'
        self.file_name_ext = f'db/{self.name}.py'
        self.fields = ""
        
        for emodel in self.odoo.search_raw('ir.model',[("model","=", self.model)]):
            print(f"Loading model {emodel['name']}")
            for field in self.odoo.search_raw('ir.model.fields',[("model","=", self.model)]):
                
                if field["name"] in ['id', 'create_uid', 'write_uid']:
                    continue
                
                read_only = False
                if field['state'] == 'base':
                    read_only = True
                
                ttype = field['ttype']

                self.field(field, read_only)

        header = ""
        header += f"\n"
        header += f"T = TypeVar('T')\n"
        header += f"\n"
        header += f"class {self.name}B(OdooDataClass):\n"
        header += f"    _MODEL = '{self.model}'\n\n"


        header += f"    def __init__(self, odoo:OdooTransaction, wo:dict[str,{self.add_import('typing','Any')}]|None = None):\n"
        header += f"        super().__init__(odoo, self._MODEL, wo)\n"
        header += f"\n"        
        
        imports = ""
        if self.type_only_forward_imports:
            imports += f"from __future__ import annotations  # This is crucial for forward references\n"
            imports += f"from typing import TYPE_CHECKING\n"
            imports += f"if TYPE_CHECKING:\n"
            for k,v in self.type_only_forward_imports.items():            
                imports += f"    from {k} import {v} # Import only when type checking\n"

        for k,v in self.imports.items():       
            imports += f"from {k} import {v}\n"

        
        complete_class = imports+header+self.fields

        try:
            with open(self.file_name_base, 'w') as f:
                f.write(complete_class)
            print(f"Code written to {self.file_name_base}")

            if not os.path.exists(self.file_name_ext):
                with open(self.file_name_ext, 'w') as f:
                    f.write(f"from db.{self.name}B import {self.name}B\nfrom typing import Any\nfrom odoo_base import OdooTransaction\n\nclass {self.name}({self.name}B):\n    def __init__(self, odoo:OdooTransaction, wo:dict[str,Any]|None = None):\n        super().__init__(odoo, wo)")


        except Exception as e:
            print(f"Error writing to file: {e}")        

odoo = OdooBackend("mixt").begin()
models = [
     Klass(odoo, "x_cd.supplier_payment", "SupplierPayment"),
     Klass(odoo, "x_cd.supplier_payment_part", "SupplierPaymentPart"),
     Klass(odoo, "x_cd.cto", "CTO"),
     Klass(odoo, "x_cd.cto_booking", "CTOBooking"),
     Klass(odoo, "x_cd.cto_booking_entry", "CTOBookingEntry"),
     Klass(odoo, "x_cd.cto_payment", "CTOPayment"),
     Klass(odoo, "x_cd.commission_forecast", "CDCommissionForecast"),
     ]

for model in models:
    model.save()

