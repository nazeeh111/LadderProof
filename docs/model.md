# Admitted model and exact extrema

The circuit is an unloaded static voltage-mode R-2R topology. With n bits there are n unknown ladder node voltages. Branch B_i connects node i to an ideal digital boundary at either zero volts or Vref. B0 is the most significant bit and node0 is the output. Series S_i joins node i to node i+1. Termination T joins the final node to ground. Values may differ from their ideal R/2R ratios; every component must remain a positive finite resistor. Switching changes the fixed boundary voltages, not resistor incidence or the reduced conductance matrix.

Every component has an independent closed resistance interval and an admitted nominal value. This is a Cartesian set of allowed combinations, not an assertion of probabilistic independence. Equal min/max endpoints describe a fixed resistor. The reference voltage is fixed and positive. No output load, nonlinear component, switch resistance, dynamic state or temperature function is included.

## Why checking corners is complete here

The reduced nodal matrix A is positive definite at every allowed assignment: its quadratic form is a sum of positive conductance-weighted squared node differences plus squared terms at edges reaching fixed-voltage boundaries. Every ladder node reaches such a boundary, so only the zero vector makes the form vanish.

Fix all resistors except one and vary its conductance from an admitted baseline g0 by t. Its reduced incidence vector v gives A(t)=A0+t vvᵀ. If it touches a boundary, the injection changes as q(t)=q0+t h v; for an internal edge h=0. Define x0=A0⁻¹q0, z=A0⁻¹v and α=vᵀz. Direct substitution yields

    x(t) = x0 + t/(1+tα) · z(h−vᵀx0).

Positive definiteness makes 1+tα positive. For a fixed linear voltage observable cᵀx, its derivative is

    (cᵀz)(h−vᵀx0)/(1+tα)².

The sign is constant with the other coordinates fixed, or zero. Resistance is the reciprocal of conductance, so its endpoint property also holds. A continuous observable attains extrema on the compact positive resistance box. Move each coordinate of a maximizing assignment to an endpoint that does not decrease the value; after all coordinates the result is a corner with the same maximum. Repeat for minima. Sensitivity signs may depend on the other components, so choosing endpoints from a single nominal sensitivity calculation is insufficient.

For adjacent codes, the same A and resistor assignment produce x_next−x_previous=A⁻¹(q_next−q_previous). This is another linear voltage observable. Enumerating every corner for this same-assignment difference is complete. Subtracting separately optimized code voltages is not generally an attained transition.

A nonnegative complete minimum step establishes nondecreasing static behavior for every admitted assignment. A zero minimum does not establish strict increase. A negative attained witness establishes that a static decrease is possible in the box. Neither outcome certifies a physical device.

## Boundaries of the argument

Sharing an uncertain variable across several resistors changes the coordinate update and can introduce interior extrema. Changing the matrix between compared states has the same problem. Power is not a fixed linear voltage observable. The application therefore does not apply this theorem to correlated values, changing topology, code-dependent nonideal switches, nonlinear components or resistor power. Gaussian sampling and yield estimation are different questions.

Worst-case enumeration is exponential in uncertain components. Limits are visible and enforced; larger ladders do not fall back to incomplete sampling under the same certificate label.
