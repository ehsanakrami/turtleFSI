from dolfin import *
from numpy import isnan
#import numpy as np


def solver_setup(F_fluid_linear, F_fluid_nonlinear,
                 F_solid_linear, F_solid_nonlinear, DVP, dvp_, up_sol, **monolithic):

    print("solver_setup")
    F_lin = F_fluid_linear + F_solid_linear
    F_nonlin = F_fluid_nonlinear + F_solid_nonlinear
    F = F_lin + F_nonlin

    chi = TrialFunction(DVP)
    J_linear = derivative(F_lin, dvp_["n"], chi)
    J_nonlinear = derivative(F_nonlin, dvp_["n"], chi)

    #A_pre = assemble(J_linear)
    A_pre = assemble(J_linear, form_compiler_parameters={"optimize": True})
    A = Matrix(A_pre)
    b = None
    up_sol.parameters['reuse_factorization'] = True

    return dict(F=F, J_nonlinear=J_nonlinear, A_pre=A_pre, A=A, b=b)


def newtonsolver(F, J_nonlinear, A_pre, A, b, bcs, DVP,
                 dvp_, up_sol, dvp_res, rtol, atol, max_it, T, t, **monolithic):
    Iter = 0
    residual = 1E7
    rel_res = residual
    lmbda = 1
    last_rel_res = 2E7  # Capture if residual increases from last iteration
    last_residual = 2E7
    Iterbottom = 7

    while rel_res > rtol and residual > atol and Iter < max_it:

        if last_rel_res < rel_res and last_residual < residual:
            print("assembling complete JAC")
            A = assemble(J_nonlinear, 
                         tensor=A,
                         keep_diagonal=True,
                         form_compiler_parameters={"optimize": True})
            # Force Full assembple without reduce
            A.axpy(1.0, A_pre, True)
            A.ident_zeros()
            [bc.apply(A) for bc in bcs]
            up_sol.set_operator(A)
            #lmbda = lmbda/2.0

        elif Iter % Iterbottom == 0:
            print("assembling CHEAP` JAC")
            A = assemble(J_nonlinear,
                         tensor=A, 
                         keep_diagonal=True, 
                         form_compiler_parameters={"optimize": True, "quadrature_degree": 4})
            A.axpy(1.0, A_pre, True)
            A.ident_zeros()
            [bc.apply(A) for bc in bcs]
            up_sol.set_operator(A)
        
        b = assemble(-F, tensor=b)
        # b = assemble(-F, tensor=b, form_compiler_parameters={"quadrature_degree": 4})
        last_rel_res = rel_res  # Capture if residual increases from last iteration
        last_residual = residual

        [bc.apply(b, dvp_["n"].vector()) for bc in bcs]
        #[bc.apply(A, b, dvp_["n"].vector()) for bc in bcs]
        up_sol.solve(dvp_res.vector(), b)
        dvp_["n"].vector().axpy(lmbda, dvp_res.vector())
        [bc.apply(dvp_["n"].vector()) for bc in bcs]
        rel_res = norm(dvp_res, 'l2')
        residual = b.norm('l2')
        if rel_res > 1E20 or residual > 1E20:
            print("IN IF TEST")
            t = T + 1
            break

        if MPI.rank(mpi_comm_world()) == 0:
            print("Newton iteration %d: r (atol) = %.3e (tol = %.3e), r (rel) = %.3e (tol = %.3e) "
                  % (Iter, residual, atol, rel_res, rtol))
        Iter += 1

    return dict(t=t)
