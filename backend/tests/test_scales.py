from scales import compute_ratio, compute_scale


def test_percentage_scale_is_fixed_to_zero_hundred():
    scale = compute_scale("porcentaje_mujeres", "municipality", 2022, [12, 45, 91])

    assert scale.domain_min == 0
    assert scale.domain_max == 100
    assert compute_ratio(50, scale) == 0.5


def test_count_scale_is_stable_for_a_subset():
    scale = compute_scale("poblacion_total", "municipality", 2022, [10, 100, 1000])

    assert compute_ratio(100, scale) == compute_ratio(100, scale)
    assert compute_ratio(1000, scale) > compute_ratio(100, scale)


def test_missing_value_has_no_analytical_ratio():
    scale = compute_scale("poblacion_total", "municipality", 2022, [10, 100])

    assert compute_ratio(None, scale) is None
