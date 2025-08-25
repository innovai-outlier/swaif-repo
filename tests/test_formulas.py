from math import isclose
from estoque.domain.formulas import (
    z_from_service_level,
    demanda_leadtime,
    sigma_leadtime,
    estoque_seguranca,
    ponto_pedido,
)

def test_z_from_service_level_typical():
    z95 = z_from_service_level(0.95)
    # referência ~1.64485 (tolerância pequena)
    assert isclose(z95, 1.64485, rel_tol=1e-3, abs_tol=1e-3)

def test_demanda_leadtime_e_sigma():
    mu_d, sigma_d = 10.0, 3.0
    mu_t, sigma_t = 6.0, 1.0
    mu_DL = demanda_leadtime(mu_d, mu_t)
    sig_DL = sigma_leadtime(mu_d, sigma_d, mu_t, sigma_t)
    assert isclose(mu_DL, 60.0, rel_tol=1e-9, abs_tol=1e-9)
    # Var = mu_t*sigma_d^2 + mu_d^2*sigma_t^2 = 6*9 + 100*1 = 54 + 100 = 154
    # sigma = sqrt(154) ≈ 12.4097
    assert isclose(sig_DL, 154 ** 0.5, rel_tol=1e-9, abs_tol=1e-9)

def test_ss_e_rop():
    z = z_from_service_level(0.95)
    sigma_DL = 12.4097
    ss = estoque_seguranca(z, sigma_DL)
    rop = ponto_pedido(60.0, ss)
    assert ss > 0
    assert rop > 60
