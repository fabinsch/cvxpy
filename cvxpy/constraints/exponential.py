"""
Copyright 2013 Steven Diamond


Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from __future__ import annotations

from typing import List, Tuple

import numpy as np

from cvxpy.constraints.constraint import Constraint
from cvxpy.expressions import cvxtypes
from cvxpy.utilities import scopes


class ExpCone(Constraint):
    """A reformulated exponential cone constraint.

    Operates elementwise on :math:`x, y, z`.

    Original cone:

    .. math::

        K = \\{(x,y,z) \\mid y > 0, ye^{x/y} <= z\\}
            \\cup \\{(x,y,z) \\mid x \\leq 0, y = 0, z \\geq 0\\}

    Reformulated cone:

    .. math::

        K = \\{(x,y,z) \\mid y, z > 0, y\\log(y) + x \\leq y\\log(z)\\}
             \\cup \\{(x,y,z) \\mid x \\leq 0, y = 0, z \\geq 0\\}

    Parameters
    ----------
    x : Variable
        x in the exponential cone.
    y : Variable
        y in the exponential cone.
    z : Variable
        z in the exponential cone.
    """

    def __init__(self, x, y, z, constr_id=None) -> None:
        Expression = cvxtypes.expression()
        self.x = Expression.cast_to_const(x)
        self.y = Expression.cast_to_const(y)
        self.z = Expression.cast_to_const(z)
        xs, ys, zs = self.x.shape, self.y.shape, self.z.shape
        if xs != ys or xs != zs:
            msg = ("All arguments must have the same shapes. Provided arguments have"
                   "shapes %s" % str((xs, ys, zs)))
            raise ValueError(msg)
        super(ExpCone, self).__init__([self.x, self.y, self.z],
                                      constr_id)

    def __str__(self) -> str:
        return "ExpCone(%s, %s, %s)" % (self.x, self.y, self.z)

    def __repr__(self) -> str:
        return "ExpCone(%s, %s, %s)" % (self.x, self.y, self.z)

    @property
    def residual(self):
        # TODO(akshayka): The projection should be implemented directly.
        from cvxpy import Minimize, Problem, Variable, hstack, norm2
        if self.x.value is None or self.y.value is None or self.z.value is None:
            return None
        x = Variable(self.x.shape)
        y = Variable(self.y.shape)
        z = Variable(self.z.shape)
        constr = [ExpCone(x, y, z)]
        obj = Minimize(norm2(hstack([x, y, z]) -
                             hstack([self.x.value, self.y.value, self.z.value])))
        problem = Problem(obj, constr)
        return problem.solve()

    @property
    def size(self) -> int:
        """The number of entries in the combined cones.
        """
        return 3 * self.num_cones()

    def num_cones(self):
        """The number of elementwise cones.
        """
        return self.x.size

    def as_quad_approx(self, m: int, k: int) -> RelEntrQuad:
        return RelEntrQuad(self.y, self.z, -self.x, m, k)

    def cone_sizes(self) -> List[int]:
        """The dimensions of the exponential cones.

        Returns
        -------
        list
            A list of the sizes of the elementwise cones.
        """
        return [3]*self.num_cones()

    def is_dcp(self, dpp: bool = False) -> bool:
        """An exponential constraint is DCP if each argument is affine.
        """
        if dpp:
            with scopes.dpp_scope():
                return all(arg.is_affine() for arg in self.args)
        return all(arg.is_affine() for arg in self.args)

    def is_dgp(self, dpp: bool = False) -> bool:
        return False

    def is_dqcp(self) -> bool:
        return self.is_dcp()

    @property
    def shape(self) -> Tuple[int, ...]:
        s = (3,) + self.x.shape
        return s

    def save_dual_value(self, value) -> None:
        # TODO(akshaya,SteveDiamond): verify that reshaping below works correctly
        value = np.reshape(value, newshape=(-1, 3))
        dv0 = np.reshape(value[:, 0], newshape=self.x.shape)
        dv1 = np.reshape(value[:, 1], newshape=self.y.shape)
        dv2 = np.reshape(value[:, 2], newshape=self.z.shape)
        self.dual_variables[0].save_value(dv0)
        self.dual_variables[1].save_value(dv1)
        self.dual_variables[2].save_value(dv2)


class RelEntrQuad(Constraint):
    """An approximate construction of the scalar relative entropy cone

    Definition:
    .. math::
        K_{re}=\text{cl}\\{(x,y,\\tau)\\in\\mathbb{R}_{++}\\times
                \\mathbb{R}_{++}\\times\\mathbb{R}_{++}\\:x\\log(x/y)\\leq\\tau\\}

    Since the above definition is very similar to the ExpCone, we provide a conversion method

    More details on the approximation can be found in Theorem-3 on page-10 in the paper:
    Semidefinite Approximations of the Matrix Logarithm.

    Parameters
    ----------
    x : Expression
        x in the (approximate) scalar relative entropy cone
    y : Expression
        y in the (approximate) scalar relative entropy cone
    $\\tau$ : Expression
        $\\tau$ in the (approximate) scalar relative entropy cone
    m: Parameter directly related to the number of generated nodes for the quadrature
    approximation used in the algorithm
    k: Another parameter controlling the approximation
    """

    def __init__(self, x, y, z, m, k, constr_id=None) -> None:
        Expression = cvxtypes.expression()
        self.x = Expression.cast_to_const(x)
        self.y = Expression.cast_to_const(y)
        self.z = Expression.cast_to_const(z)
        self.m = m
        self.k = k
        xs, ys, zs = self.x.shape, self.y.shape, self.z.shape
        if xs != ys or xs != zs:
            msg = ("All arguments must have the same shapes. Provided arguments have"
                   "shapes %s" % str((xs, ys, zs)))
            raise ValueError(msg)
        super(RelEntrQuad, self).__init__([self.x, self.y, self.z], constr_id)

    def get_data(self):
        return [self.m, self.k]

    def __str__(self) -> str:
        tup = (self.x, self.y, self.z, self.m, self.k)
        return "RelEntrQuad(%s, %s, %s, %s, %s)" % tup

    def __repr__(self) -> str:
        return self.__str__()

    @property
    def residual(self):
        # TODO(akshayka): The projection should be implemented directly.
        from cvxpy import Minimize, Problem, Variable, hstack, norm2
        if self.x.value is None or self.y.value is None or self.z.value is None:
            return None
        cvxtypes.expression()
        x = Variable(self.x.shape)
        y = Variable(self.y.shape)
        z = Variable(self.z.shape)
        constr = [RelEntrQuad(x, y, z, self.m, self.k)]
        obj = Minimize(norm2(hstack([x, y, z]) -
                             hstack([self.x.value, self.y.value, self.z.value])))
        problem = Problem(obj, constr)
        return problem.solve()

    @property
    def size(self) -> int:
        """The number of entries in the combined cones.
        """
        return 3 * self.num_cones()

    def num_cones(self):
        """The number of elementwise cones.
        """
        return self.x.size

    def cone_sizes(self) -> List[int]:
        """The dimensions of the exponential cones.

        Returns
        -------
        list
            A list of the sizes of the elementwise cones.
        """
        return [3]*self.num_cones()

    def is_dcp(self, dpp: bool = False) -> bool:
        """An exponential constraint is DCP if each argument is affine.
        """
        if dpp:
            with scopes.dpp_scope():
                return all(arg.is_affine() for arg in self.args)
        return all(arg.is_affine() for arg in self.args)

    def is_dgp(self, dpp: bool = False) -> bool:
        return False

    def is_dqcp(self) -> bool:
        return self.is_dcp()

    @property
    def shape(self) -> Tuple[int, ...]:
        s = (3,) + self.x.shape
        return s

    def save_dual_value(self, value) -> None:
        # TODO: implement me.
        return
