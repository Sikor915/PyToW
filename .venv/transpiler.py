import ast

# Need to add:
# - arrays - proper implementation with iterating over the array
# - proper I/O (input, print) - it needs to be something like out_<var>: rst'<value>'
# - strings - don't know what to do with them, the code can print them right now but nothing else really
# - stack implementation - functions and things of that nature
class PythonToWTranspiler(ast.NodeVisitor):

    def __init__(self):
        self.instructions = []
        self.variables = {}
        self.label_counter = 0
        self.for_label_counter = 0
        self.table_invoke_counter = 0
        self.varDict = {}
        self.arrays = {}
        self.strings = {}

    def get_label(self, var_name):
        if var_name not in self.variables:
            self.variables[var_name] = f"var_{var_name}"
        return self.variables[var_name]

    def new_label(self):
        label = f"L{self.label_counter}"
        self.label_counter += 1
        return label

    def new_for_label(self):
        label = f"forEnd_{self.for_label_counter}"
        self.for_label_counter += 1
        return label

    def get_new_table_invoke_label(self, table_name):
        label = table_name + "Addr" + str(self.table_invoke_counter)
        self.table_invoke_counter += 1
        return label

    def make_tab_line(self, value):
        return f"rst {value}" if value is not None else "rpa"

    def transpile(self, source_code):
        tree = ast.parse(source_code)
        self.visit(tree)
        self.instructions.append("stp")
        self.instructions.append("")
        for label, value in self.varDict.items():
            if(value is not None):
                self.instructions.append(f"{label}: rst {value}")
            else:
                self.instructions.append(f"{label}: rpa")

        for base_label, char_list in self.strings.items():
            self.instructions.append(f"{base_label}: rst '{char_list[0]}'")
            for ch in char_list[1:]:
                self.instructions.append(f"       rst '{ch}'")

        for base_label, values in self.arrays.items():
            self.instructions.append(f"{base_label}: {self.make_tab_line(values[0])}")
            for v in values[1:]:
                self.instructions.append(f"       {self.make_tab_line(v)}")

        return "\n".join(self.instructions)

    def visit_Assign(self, node):
        if isinstance(node.value, ast.Constant) and not isinstance(node.targets[0], ast.Subscript):
            if not isinstance(node.value.value, str):
                label = self.get_label(node.targets[0].id)
                value = node.value.value
                self.varDict[label] = value
            else:
                base_label = self.get_label(node.targets[0].id)
                s = node.value.value
                stringSize = len(s)
                char_list = list(s) if s else ['0']
                self.strings[base_label] = char_list
                self.varDict[base_label + "Size"] = stringSize
                self.varDict[base_label + "Size_temp"] = 0
        elif isinstance(node.value, ast.BinOp):
            # DODAJ OBSŁUGĘ OPERACJI W STYLU x = tab[i] + tab[j]   ------------------------------------------------------
            # TO BĘDZIE WYMAGAŁO SPOREJ PRZEBUDOWY TEJ CZĘSCI KODU ------------------------------------------------------
            left_label = self.get_operand_label(node.value.left)
            right_label = self.get_operand_label(node.value.right)
            result_label = self.get_label(node.targets[0].id)
            if result_label not in self.varDict: self.varDict[result_label] = None
            op_map = {
                ast.Add: "dod",
                ast.Sub: "ode",
                ast.Mult: "mno",
                ast.Div: "dzi"
            }
            op_instr = op_map[type(node.value.op)]
            self.instructions.append(f"pob {left_label}")
            self.instructions.append(f"{op_instr} {right_label}")
            self.instructions.append(f"ład {result_label}")
        elif isinstance(node.value, ast.List):
            base_label = self.get_label(node.targets[0].id)
            values = []
            listSize = len(node.value.elts)
            for elt in node.value.elts:
                if isinstance(elt, ast.Constant):
                    values.append(elt.value)
                else:
                    values.append(0)
            if not values:
                values = [0]
            self.varDict[base_label + "Size"] = listSize
            self.varDict[base_label + "Size_temp"] = 0
            self.arrays[base_label] = values
        elif isinstance(node.value, ast.Name) and not isinstance(node.targets[0], ast.Subscript):
            source_label = self.get_label(node.value.id)
            target_label = self.get_label(node.targets[0].id)
            if target_label not in self.varDict: self.varDict[target_label] = None
            self.instructions.append(f"pob {source_label}")
            self.instructions.append(f"ład {target_label}")
        elif isinstance(node.targets[0], ast.Subscript):
            array_name = "var_" + node.targets[0].value.id
            if node.targets[0].slice is ast.Constant:
                index_expr = node.targets[0].slice.value
            else:
                index_expr = node.targets[0].slice.id
            if isinstance(node.value, ast.Constant):
                value_expr = node.value.value
            else:
                value_expr = node.value.id

            addr_label = self.get_new_table_invoke_label(array_name)
            temp_addr_label = f"{addr_label}Temp"
            if temp_addr_label not in self.varDict: self.varDict[temp_addr_label] = 0
            value_label = self.get_label(value_expr)
            index_label = self.get_label(index_expr)
            if value_label not in self.varDict: self.varDict[value_label] = value_expr

            self.instructions.append(f"pob {addr_label}")
            self.instructions.append(f"ład {temp_addr_label}")
            self.instructions.append(f"dod {index_label}")
            self.instructions.append(f"ład {addr_label}")
            self.instructions.append(f"pob {value_label}")
            self.instructions.append(f"{addr_label}: ład {array_name}")
            self.instructions.append(f"pob {temp_addr_label}")
            self.instructions.append(f"ład {addr_label}")
        elif isinstance(node.value, ast.Subscript) and not isinstance(node.targets[0], ast.Subscript):
            array_name = "var_" + node.value.value.id
            target_label = self.get_label(node.targets[0].id)
            addr_label = self.get_new_table_invoke_label(array_name)
            temp_addr_label = f"{addr_label}Temp"
            if temp_addr_label not in self.varDict: self.varDict[temp_addr_label] = 0
            if target_label not in self.varDict: self.varDict[target_label] = None

            index_expr = None
            if isinstance(node.value.slice, ast.BinOp):
                op_map = {
                    ast.Add: "dod",
                    ast.Sub: "ode",
                    ast.Mult: "mno",
                    ast.Div: "dzi"
                }
                left_expr = node.value.slice.left.id if isinstance(node.value.slice.left,
                                                                   ast.Name) else node.value.slice.left.value
                right_expr = node.value.slice.right.id if isinstance(node.value.slice.right,
                                                                     ast.Name) else node.value.slice.right.value
                op_expr = op_map[type(node.value.slice.op)]
                left_label = self.get_label(left_expr)
                right_label = self.get_label(right_expr)
                if left_label not in self.varDict: self.varDict[left_label] = left_expr if isinstance(left_expr, int) else  None
                if right_label not in self.varDict: self.varDict[right_label] = right_expr if isinstance(right_expr, int) else  None

                index_result = self.get_label("index_result")
                if index_result not in self.varDict: self.varDict[index_result] = None

                self.instructions.append(f"pob {left_label}")
                self.instructions.append(f"{op_expr} {right_label}")
                self.instructions.append(f"ład {index_result}")
                index_label = index_result
            elif isinstance(node.value.slice, ast.Constant):
                index_expr = node.value.slice.value
                index_label = self.get_label(index_expr)
            elif isinstance(node.value.slice, ast.Name):
                index_expr = node.value.slice.id
                index_label = self.get_label(index_expr)

            self.instructions.append(f"pob {addr_label}")
            self.instructions.append(f"ład {temp_addr_label}")
            self.instructions.append(f"dod {index_label}")
            self.instructions.append(f"ład {addr_label}")
            self.instructions.append(f"{addr_label}: pob {array_name}")
            self.instructions.append(f"ład {target_label}")
            self.instructions.append(f"pob {temp_addr_label}")
            self.instructions.append(f"ład {addr_label}")

        else:
            raise NotImplementedError("Unsupported assignment operation.")

    def visit_AugAssign(self, node):
        target_label = self.get_label(node.target.id)
        right_label = self.get_operand_label(node.value)
        op_map = {
            ast.Add: "dod",
            ast.Sub: "ode",
            ast.Mult: "mno",
            ast.Div: "dzi"
        }
        op_instr = op_map[type(node.op)]
        self.instructions.append(f"pob {target_label}")
        self.instructions.append(f"{op_instr} {right_label}")
        self.instructions.append(f"ład {target_label}")

    def visit_Compare(self, node):
        left_label = self.get_operand_label(node.left)
        right_label = self.get_operand_label(node.comparators[0])
        self.instructions.append(f"pob {left_label}")
        self.instructions.append(f"ode {right_label}")

        label_true = self.new_label()
        label_false = self.new_label()

        if isinstance(node.ops[0], ast.Gt):
            var_neg1 = "var_neg1"
            self.varDict[var_neg1] = -1
            self.instructions.append(f"mno {var_neg1}")
            self.instructions.append(f"som {label_true}")  # Jeśli ACC < 0, skocz do false
            self.instructions.append(f"sob {label_false}")  # W przeciwnym razie skocz do false
        elif isinstance(node.ops[0], ast.Lt):
            self.instructions.append(f"som {label_true}")  # Jeśli ACC < 0, skocz do true
            self.instructions.append(f"sob {label_false}")  # W przeciwnym razie skocz do false
        elif isinstance(node.ops[0], ast.GtE):
            var_neg1 = "var_neg1"
            self.varDict[var_neg1] = -1
            self.instructions.append(f"mno {var_neg1}")
            self.instructions.append(f"som {label_true}")  # Jeśli ACC < 0, skocz do false
            self.instructions.append(f"soz {label_true}")  # Jeśli ACC == 0, skocz do false
            self.instructions.append(f"sob {label_false}")  # W przeciwnym razie skocz do false
        elif isinstance(node.ops[0], ast.LtE):
            self.instructions.append(f"som {label_true}")  # Jeśli ACC < 0, skocz do false
            self.instructions.append(f"soz {label_true}")  # Jeśli ACC == 0, skocz do false
            self.instructions.append(f"sob {label_false}")  # W przeciwnym razie skocz do false
        elif isinstance(node.ops[0], ast.Eq):
            self.instructions.append(f"soz {label_true}")  # Jeśli ACC == 0, skocz do true
            self.instructions.append(f"sob {label_false}")  # W przeciwnym razie skocz do false
        elif isinstance(node.ops[0], ast.NotEq):
            self.instructions.append(f"soz {label_false}")  # Jeśli ACC == 0, skocz do false

        return label_true, label_false

    def visit_If(self, node):
        label_true, label_false = self.visit_Compare(node.test)
        end_label = self.new_label()

        self.instructions.append(f"{label_true}:")
        for stmt in node.body:
            self.visit(stmt)
        self.instructions.append(f"sob {end_label}")

        self.instructions.append(f"{label_false}:")
        for stmt in node.orelse:
            self.visit(stmt)

        self.instructions.append(f"{end_label}:")

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "print":
            arg = node.value.args[0]
            if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute) and arg.func.attr == "len":
                base_name = arg.func.value.id
                size_var = f"var_{base_name}Size"
                self.instructions.append(f"pob {size_var}")
                self.instructions.append("wyp 2")
            elif isinstance(arg, ast.Name):
                var_name = arg.id
                label = self.get_label(var_name)
                if label in self.strings:
                    size_label = self.get_label(var_name + "Size")
                    size_label_temp = self.get_label(var_name + "Size_temp")
                    self.instructions.append(f"pob {size_label}")
                    self.instructions.append(f"ład {size_label_temp}")
                    self.generate_read_table(label, size_label_temp)

                else:
                    self.instructions.append(f"pob {label}")
                    self.instructions.append("wyp 2")
            else:
                self.instructions.append("wyp 2")
        elif isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "append":
            array_name = "var_" + node.value.func.value.id
            size_label = f"{array_name}Size"
            addr_label = self.get_new_table_invoke_label(array_name)
            temp_addr_label = f"{addr_label}Temp"
            if temp_addr_label not in self.varDict: self.varDict[temp_addr_label] = 0
            var_1 = "var_1"
            if var_1 not in self.varDict: self.varDict[var_1] = 1

            if isinstance(node.value.args[0], ast.Constant):
                append_value = node.value.args[0].value
                append_label = self.get_label(append_value)
                if append_label not in self.varDict: self.varDict[append_label] = append_value
            elif isinstance(node.value.args[0], ast.Name):
                append_value = node.value.args[0].id
                append_label = self.get_label(append_value)

            self.instructions.append(f"pob {addr_label}")
            self.instructions.append(f"ład {temp_addr_label}")
            self.instructions.append(f"dod {size_label}")
            self.instructions.append(f"ład {addr_label}")
            self.instructions.append(f"pob {size_label}")
            self.instructions.append(f"dod {var_1}")
            self.instructions.append(f"ład {size_label}")
            self.instructions.append(f"pob {append_label}")
            self.instructions.append(f"{addr_label}: ład {array_name}")
            self.instructions.append(f"pob {temp_addr_label}")
            self.instructions.append(f"ład {addr_label}")
        else:
            raise NotImplementedError("Unsupported expression type.")

    def get_operand_label(self, operand):
        if isinstance(operand, ast.Constant):
            label = self.get_label(operand.value)
            self.varDict[label] = operand.value
            return label
        elif isinstance(operand, ast.Name):
            return self.get_label(operand.id)
        else:
            raise NotImplementedError("Unsupported operand type.")

    def get_for_label(self, operand):
        if isinstance(operand, ast.Constant):
            label = self.new_for_label()
            self.varDict[label] = operand.value
            return label
        elif isinstance(operand, ast.Name):
            return self.get_label(operand.id)
        else:
            raise NotImplementedError("Unsupported operand type.")

    def visit_For(self, node):
        if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range":
            loop_var = self.get_label(node.target.id)
            start_label = self.new_label()
            end_label = self.new_label()

            if len(node.iter.args) == 1:
                start_value = 0
                loop_end = self.get_for_label(node.iter.args[0])
                step = "var_1"
                self.varDict["var_1"] = 1
            elif len(node.iter.args) == 2:
                start_value = node.iter.args[0].value
                loop_end = self.get_for_label(node.iter.args[1])
                step = "var_1"
                self.varDict["var_1"] = 1
            elif len(node.iter.args) == 3:
                start_value = node.iter.args[0].value
                loop_end = self.get_for_label(node.iter.args[1])
                if isinstance(node.iter.args[2], ast.UnaryOp) and isinstance(node.iter.args[2].op, ast.USub):
                    step_value = -node.iter.args[2].operand.value
                else:
                    step_value = node.iter.args[2].value
                step_label = f"var_{step_value}"
                self.varDict[step_label] = step_value
                step = step_label

            self.varDict[loop_var] = start_value

            self.instructions.append(f"{start_label}:")
            self.instructions.append(f"pob {loop_var}")
            self.instructions.append(f"ode {loop_end}")
            self.instructions.append(f"soz {end_label}")
            for stmt in node.body:
                self.visit(stmt)
            self.instructions.append(f"pob {loop_var}")
            self.instructions.append(f"dod {step}")
            self.instructions.append(f"ład {loop_var}")
            self.instructions.append(f"sob {start_label}")
            self.instructions.append(f"{end_label}:")
        else:
            raise NotImplementedError("Unsupported for-loop type.")

    def visit_While(self, node):
        loop_start = self.new_label()

        self.instructions.append(f"{loop_start}:")

        label_true, label_false = self.visit_Compare(node.test)
        self.instructions.append(f"{label_true}:")
        for stmt in node.body:
            self.visit(stmt)

        self.instructions.append(f"sob {loop_start}")
        self.instructions.append(f"{label_false}:")

    def generate_read_table(self, base_label, size_label):

        var_1 = "var_1"
        self.varDict[var_1] = 1

        loop_label = self.new_label()
        end_label = self.new_label()

        self.instructions.append(f"{loop_label}:")
        self.instructions.append(f"pob {base_label}")
        self.instructions.append("wyp 2")

        self.instructions.append(f"pob {size_label}")
        self.instructions.append(f"ode {var_1}")
        self.instructions.append(f"ład {size_label}")

        self.instructions.append(f"soz {end_label}")

        self.instructions.append(f"pob {loop_label}")
        self.instructions.append(f"dod {var_1}")
        self.instructions.append(f"ład {loop_label}")

        self.instructions.append(f"sob {loop_label}")
        self.instructions.append(f"{end_label}:")

# Example usage
source_code = """
n = 3
fib = [0, 1]
if n > 2:
    for i in range (2, n):
        old = fib[i-1]
        new = fib[i]
        curr = fib[i+2]
"""

transpiler = PythonToWTranspiler()
w_code = transpiler.transpile(source_code)
print(w_code)
