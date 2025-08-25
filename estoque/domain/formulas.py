"""
Mathematical formulas for stock planning.

These functions implement the core statistical formulas used in
continuous review inventory systems. Given demand statistics and
target service levels they return values such as safety stock and
reorder points. The formulas mirror those documented in the
functions specification.

All functions are pure: they depend solely on their inputs and do
not modify any external state. This makes them safe to unit test
individually.
"""

from math import sqrt
from typing import Union

try:
    # SciPy provides the inverse CDF (percent point function) for the normal
    # distribution. We wrap the import in a try/except so that unit tests
    # without SciPy can still run by providing a fallback approximation.
    from scipy.stats import norm  # type: ignore
    _has_scipy = True
except Exception:
    _has_scipy = False


def z_from_service_level(nivel_servico: float) -> float:
    """Return the z-score corresponding to a given service level.

    Parameters
    ----------
    nivel_servico: float
        Desired cycle service level expressed as a probability (0 < p < 1).

    Returns
    -------
    float
        The z-score such that Φ(z) = nivel_servico where Φ is the CDF of
        the standard normal distribution.
    """
    if nivel_servico is None:
        raise ValueError("nivel_servico must be provided")
    if not (0.0 < nivel_servico < 1.0):
        raise ValueError("nivel_servico must be between 0 and 1")
    if _has_scipy:
        return float(norm.ppf(nivel_servico))
    # Fallback approximation using an inverse error function.
    import math
    a1 = -39.69683028665376
    a2 = 220.9460984245205
    a3 = -275.9285104469687
    a4 = 138.3577518672690
    a5 = -30.66479806614716
    a6 = 2.506628277459239
    b1 = -54.47609879822406
    b2 = 161.5858368580409
    b3 = -155.6989798598866
    b4 = 66.80131188771972
    b5 = -13.28068155288572
    p = nivel_servico
    if p < 0.5:
        t = math.sqrt(-2.0 * math.log(p))
    else:
        t = math.sqrt(-2.0 * math.log(1.0 - p))
    num = ((((a1 * t + a2) * t + a3) * t + a4) * t + a5) * t + a6
    den = ((((b1 * t + b2) * t + b3) * t + b4) * t + b5) * t + 1.0
    z = num / den
    return -z if p < 0.5 else z


def demanda_leadtime(mu_d: Union[int, float], mu_t: Union[int, float]) -> float:
    """Compute the expected demand during the replenishment lead time.

    It is assumed that demand and lead time are independent. For a given
    average daily demand `mu_d` and a mean lead time `mu_t` in days, the
    expected demand during lead time is simply the product of the two.
    """
    return float(mu_d) * float(mu_t)


def sigma_leadtime(
    mu_d: Union[int, float],
    sigma_d: Union[int, float],
    mu_t: Union[int, float],
    sigma_t: Union[int, float],
) -> float:
    """Compute the standard deviation of demand during the lead time.

    When both the daily demand and the lead time are random variables,
    independence is assumed between them. The variance of the demand
    during lead time is given by:

        Var(DL) = mu_t * sigma_d^2 + mu_d^2 * sigma_t^2

    The standard deviation is the square root of this variance.
    """
    mu_d = float(mu_d)
    sigma_d = float(sigma_d)
    mu_t = float(mu_t)
    sigma_t = float(sigma_t)
    var = mu_t * (sigma_d ** 2) + (mu_d ** 2) * (sigma_t ** 2)
    return sqrt(var) if var > 0.0 else 0.0


def estoque_seguranca(z: float, sigma_DL: float) -> float:
    """Compute the safety stock."""
    return float(z) * float(sigma_DL)


def ponto_pedido(mu_DL: float, SS: float) -> float:
    """Compute the reorder point (ROP)."""
    return float(mu_DL) + float(SS)
