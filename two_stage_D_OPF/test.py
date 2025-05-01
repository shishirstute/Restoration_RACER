from pyomo.environ import *

# Create model
model = ConcreteModel()

# Set
model.I = RangeSet(2)

# Variables
model.x = Var(model.I, bounds = (1,2))

# Mutable Parameter
model.P = Param(model.I, initialize={1: 2, 2: 3}, mutable=True)

# ✅ Correct objective using rule
# def obj_rule(m):
#     return sum(m.P[i] * m.x[i] for i in m.I)

model.obj = Objective(expr=sum(model.P[i] * model.x[i] for i in model.I), sense=minimize)

# Simple constraint so solution is bounded
# model.cons = Constraint(expr=sum(model.x[i] for i in model.I) == 1)

# Solve once
solver = SolverFactory('gurobi')
result1 = solver.solve(model)
print("Objective after 1st solve:", value(model.obj))

# 🔄 Update mutable Param
model.P[1].set_value(100)
model.P[2].set_value(200)

# Solve again
result2 = solver.solve(model)
print("Objective after 2nd solve (should be higher):", value(model.obj))
