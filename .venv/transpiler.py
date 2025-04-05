import ast
# Need to add:
# - arrays - proper implementation with iterating over the array, writing, append
# - proper I/O (input, print) - it needs to be something like out_<var>: rst'<value>'
# - strings - don't know what to do with them, the code can print them right now but nothing else really
# - stack implementation - functions and things of that nature
class PythonToWTranspiler(ast.NodeVisitor):

    def __init__(self):
        self.instructions = []
        self.variables = {}
        self.label_counter = 0
        self.for_label_counter = 0
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

    def _make_tab_line(self, value):
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
            # Pierwsza linia z etykietą bazową
            self.instructions.append(f"{base_label}: {self._make_tab_line(values[0])}")
            for v in values[1:]:
                self.instructions.append(f"       {self._make_tab_line(v)}")

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
        elif isinstance(node.value, ast.Name):
            source_label = self.get_label(node.value.id)
            target_label = self.get_label(node.targets[0].id)
            if target_label not in self.varDict: self.varDict[target_label] = None
            self.instructions.append(f"pob {source_label}")
            self.instructions.append(f"ład {target_label}")
        # DOKOŃCZ PISANIE PRZYPISANIA DO TABLICY ----------------------------------------------------------------------------
        elif isinstance(node.targets[0], ast.Subscript):
            array_name = "var_" + node.targets[0].value.id
            index_expr = node.targets[0].slice.value

            value_expr = node.value
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
            if isinstance(arg, ast.Name):
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
        else:
            raise NotImplementedError("Unsupported expression type.")

    def get_operand_label(self, operand):
        if isinstance(operand, ast.Constant):
            label = self.new_label()
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
# source_code = """
# x = 5
# y = 10
# a = []
# while x < y:
#     x = x + 1
# print(x)
# x += 5
# while x >= 0:
#     x = x - 1
# """
source_code = """
s = "Hello"
list = [1,2,3]
n = 10
cur = 1
old = 0
i = 1
print(s)
list[2] = 5
while (i < n):
    temp = cur
    cur += old 
    old = temp
    i +=1 
"""
table = [1,2,3]
transpiler = PythonToWTranspiler()
w_code = transpiler.transpile(source_code)
print(w_code)
