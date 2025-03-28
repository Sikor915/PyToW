import ast
# Need to add:
# - strings - a table of chars at the end of vars declaration like that:
#   tab: rst <value>
#        rst <value>
#        rst <value>
#           ...
# - proper I/O (input, print) - it needs to be something like out_<var>: rst'<value>'
class PythonToWTranspiler(ast.NodeVisitor):

    def __init__(self):
        self.instructions = []
        self.variables = {}
        self.label_counter = 0
        self.for_label_counter = 0
        self.varDict = {}

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

    def transpile(self, source_code):
        tree = ast.parse(source_code)
        self.visit(tree)
        self.instructions.append("stp")
        self.instructions.append("")
        for label, value in self.varDict.items():
            self.instructions.append(f"{label}: rst {value}")
        return "\n".join(self.instructions)

    def visit_Assign(self, node):
        if isinstance(node.value, ast.Constant):
            label = self.get_label(node.targets[0].id)
            value = node.value.value
            self.varDict[label] = value
        elif isinstance(node.value, ast.BinOp):
            left_label = self.get_operand_label(node.value.left)
            right_label = self.get_operand_label(node.value.right)
            result_label = self.get_label(node.targets[0].id)
            if result_label not in self.varDict: self.varDict[result_label] = ""
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
            self.instructions.append(f"mno var_neg1")
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
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
            if node.value.func.id == "print":
                var_label = self.get_operand_label(node.value.args[0])
                self.instructions.append(f"pob {var_label}")
                self.instructions.append("wyp 2")
            else:
                raise NotImplementedError(f"Function {node.value.func.id} not supported.")
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

# Example usage
source_code = """
x = 5
y = 10
while x < y:
    x = x + 1
print(x)
x += 5
while x >= 0:
    x = x - 1
"""
transpiler = PythonToWTranspiler()
w_code = transpiler.transpile(source_code)
print(w_code)
