
import pytest
import math
import random

from scenic.syntax.translator import InterpreterParseError
from tests.utils import compileScenic, sampleEgo, sampleParamP

## Utilities

def lazyTestScenario(expr, offset='0'):
    """Scenario for testing a lazily-evaluated value inside a distribution.

    Here the value 'x' lazily evaluates to 1.
    """
    return compileScenic(
        'vf = VectorField("Foo", lambda pos: 2 * pos.x)\n'
        f'x = {offset} relative to vf\n'
        f'ego = Object at 0.5 @ 0, facing {expr}'
    )

## Options and Uniform

def test_options_empty_domain():
    with pytest.raises(InterpreterParseError):
        compileScenic('x = Options([])')
    with pytest.raises(InterpreterParseError):
        compileScenic('x = Options({})')
    with pytest.raises(InterpreterParseError):
        compileScenic('x = Uniform()')

def test_options_invalid_weight():
    with pytest.raises(InterpreterParseError):
        compileScenic('x = Options({0: 1, 1: -2})')
    with pytest.raises(InterpreterParseError):
        compileScenic('x = Options({0: 1, 1: []})')
    with pytest.raises(InterpreterParseError):
        compileScenic('x = Options({0: 1, 1: (3, 5)})')

def test_uniform_interval_wrong_type():
    with pytest.raises(InterpreterParseError):
        compileScenic('x = ([], 4)')
    with pytest.raises(InterpreterParseError):
        compileScenic('x = (-10, [])')

def test_uniform_interval():
    scenario = compileScenic('ego = Object at (100, 200) @ 0')
    xs = [sampleEgo(scenario).position.x for i in range(60)]
    assert all(100 <= x <= 200 for x in xs)
    assert any(x < 150 for x in xs)
    assert any(150 < x for x in xs)

def test_uniform_discrete():
    scenario = compileScenic('ego = Object at Uniform(1, 2, 3.4) @ 0')
    xs = [sampleEgo(scenario).position.x for i in range(100)]
    assert all(x == 1 or x == 2 or x == 3.4 for x in xs)
    assert any(x == 1 for x in xs)
    assert any(x == 2 for x in xs)
    assert any(x == 3.4 for x in xs)

def test_uniform_discrete_lazy():
    scenario = lazyTestScenario('Uniform(1.2, x)')
    hs = [sampleEgo(scenario).heading for i in range(60)]
    assert all(h == 1.2 or h == pytest.approx(1) for h in hs)
    assert any(h == 1.2 for h in hs)
    assert any(h == pytest.approx(1) for h in hs)

def test_options():
    scenario = compileScenic('ego = Object at Options({0: 1, 1: 9}) @ 0')
    xs = [sampleEgo(scenario).position.x for i in range(400)]
    assert all(x == 0 or x == 1 for x in xs)
    assert sum(xs) >= 300

def test_options_lazy():
    scenario = lazyTestScenario('Options({0: 1, x: 9})')
    hs = [sampleEgo(scenario).heading for i in range(400)]
    assert all(h == 0 or h == pytest.approx(1) for h in hs)
    assert sum(hs) >= 300

## Functions, methods, attributes, operators

def test_function():
    scenario = compileScenic('ego = Object at sin(Uniform(45 deg, 90 deg)) @ 0')
    xs = [sampleEgo(scenario).position.x for i in range(60)]
    valA, valB = (pytest.approx(math.sin(math.radians(a))) for a in (45, 90))
    assert all(x == valA or x == valB for x in xs)
    assert any(x == valA for x in xs)
    assert any(x == valB for x in xs)

def test_function_lazy():
    scenario = lazyTestScenario('hypot(Uniform(5, 35), 12 * x)')
    hs = [sampleEgo(scenario).heading for i in range(60)]
    assert all(h == pytest.approx(13) or h == pytest.approx(37) for h in hs)
    assert any(h == pytest.approx(13) for h in hs)
    assert any(h == pytest.approx(37) for h in hs)

def test_function_lazy_2():
    scenario = lazyTestScenario('sin(x * 90 deg)', offset='Uniform(-1, 0)')
    hs = [sampleEgo(scenario).heading for i in range(60)]
    assert all(h == pytest.approx(0) or h == pytest.approx(1) for h in hs)
    assert any(h == pytest.approx(0) for h in hs)
    assert any(h == pytest.approx(1) for h in hs)

def test_method():
    scenario = compileScenic(
        'field = VectorField("Foo", lambda pos: pos[1])\n'
        'ang = field[0 @ (100, 200)]\n'
        'ego = Object facing ang'
    )
    angles = [sampleEgo(scenario).heading for i in range(60)]
    assert all(100 <= x <= 200 for x in angles)
    assert any(x < 150 for x in angles)
    assert any(150 < x for x in angles)

def test_method_lazy():
    # There are no distributionMethods built into the core language at this time,
    # so we need to define our own
    scenario = compileScenic(
        'from scenic.core.distributions import distributionMethod\n'
        'class Foo:\n'
        '    @distributionMethod\n'
        '    def bar(self, arg):\n'
        '        return -arg\n'
        'vf = VectorField("Baz", lambda pos: 1 + pos.x)\n'
        'ego = Object facing Foo().bar((100, 200) * (0 relative to vf))'
    )
    angles = [sampleEgo(scenario).heading for i in range(60)]
    assert all(-200 <= x <= -100 for x in angles)
    assert any(x < -150 for x in angles)
    assert any(-150 < x for x in angles)

def test_method_lazy_2():
    # See previous comment
    scenario = compileScenic(
        'from scenic.core.distributions import distributionMethod\n'
        'class Foo:\n'
        '    @distributionMethod\n'
        '    def bar(self, arg):\n'
        '        return -arg * (100, 200)\n'
        'vf = VectorField("Baz", lambda pos: 1 + pos.x)\n'
        'ego = Object facing Foo().bar(0 relative to vf)'
    )
    angles = [sampleEgo(scenario).heading for i in range(60)]
    assert all(-200 <= x <= -100 for x in angles)
    assert any(x < -150 for x in angles)
    assert any(-150 < x for x in angles)

def test_attribute():
    scenario = compileScenic(
        'place = Uniform(1 @ 1, 2 @ 4, 3 @ 9)\n'
        'ego = Object at place.x @ place.y'
    )
    xs = [sampleEgo(scenario).position.x for i in range(100)]
    assert all(x == 1 or x == 2 or x == 3 for x in xs)
    assert any(x == 1 for x in xs)
    assert any(x == 2 for x in xs)
    assert any(x == 3 for x in xs)

def test_operator():
    scenario = compileScenic('ego = Object at -(100 + (0, 100)) @ 0')
    xs = [sampleEgo(scenario).position.x for i in range(60)]
    assert all(-200 <= x <= -100 for x in xs)
    assert any(x < -150 for x in xs)
    assert any(-150 < x for x in xs)

def test_operator_lazy():
    scenario = lazyTestScenario('Uniform(0, 1) * x')
    hs = [sampleEgo(scenario).heading for i in range(60)]
    assert all(h == pytest.approx(0) or h == pytest.approx(1) for h in hs)
    assert any(h == pytest.approx(0) for h in hs)
    assert any(h == pytest.approx(1) for h in hs)

## Vectors

def test_vector_operator():
    scenario = compileScenic('ego = Object at (-3, 3) @ 0 + (100, 110) @ 0')
    xs = [sampleEgo(scenario).position.x for i in range(100)]
    assert all(97 <= x <= 113 for x in xs)
    assert any(x < 105 for x in xs)
    assert any(105 < x for x in xs)

def test_vector_method_lazy():
    scenario = lazyTestScenario('vf.followFrom(Uniform(0, 90 deg) @ 0, x, steps=1).y')
    hs = [sampleEgo(scenario).heading for i in range(60)]
    assert all(h == pytest.approx(1) or h == pytest.approx(-1) for h in hs)
    assert any(h == pytest.approx(1) for h in hs)
    assert any(h == pytest.approx(-1) for h in hs)

def test_vector_method_lazy_2():
    scenario = lazyTestScenario('vf.followFrom(90 deg @ 0, x, steps=1).y')
    h = sampleEgo(scenario).heading
    assert h == pytest.approx(-1)

## Lists, tuples, namedtuples

def test_list():
    scenario = compileScenic('ego = Object with foo [3, Uniform(1, 2)]')
    ts = [sampleEgo(scenario).foo for i in range(60)]
    assert all(type(t) is list for t in ts)
    assert all(t[0] == 3 for t in ts)
    assert all(t[1] == 1 or t[1] == 2 for t in ts)
    assert any(t[1] == 1 for t in ts)
    assert any(t[1] == 2 for t in ts)

def test_list_param():
    scenario = compileScenic('ego = Object\n' 'param p = [3, Uniform(1, 2)]')
    ts = [sampleParamP(scenario) for i in range(60)]
    assert all(type(t) is list for t in ts)
    assert all(t[0] == 3 for t in ts)
    assert all(t[1] == 1 or t[1] == 2 for t in ts)
    assert any(t[1] == 1 for t in ts)
    assert any(t[1] == 2 for t in ts)

def test_tuple():
    scenario = compileScenic('ego = Object with foo tuple([3, Uniform(1, 2)])')
    ts = [sampleEgo(scenario).foo for i in range(60)]
    assert all(type(t) is tuple for t in ts)
    assert all(t[0] == 3 for t in ts)
    assert all(t[1] == 1 or t[1] == 2 for t in ts)
    assert any(t[1] == 1 for t in ts)
    assert any(t[1] == 2 for t in ts)

def test_tuple_param():
    scenario = compileScenic('ego = Object\n' 'param p = tuple([3, Uniform(1, 2)])')
    ts = [sampleParamP(scenario) for i in range(60)]
    assert all(type(t) is tuple for t in ts)
    assert all(t[0] == 3 for t in ts)
    assert all(t[1] == 1 or t[1] == 2 for t in ts)
    assert any(t[1] == 1 for t in ts)
    assert any(t[1] == 2 for t in ts)

def test_namedtuple():
    scenario = compileScenic(
        'from collections import namedtuple\n'
        'Data = namedtuple("Data", ["bar", "baz"])\n'
        'ego = Object with foo Data(bar=3, baz=Uniform(1, 2))'
    )
    ts = [sampleEgo(scenario).foo for i in range(60)]
    assert all(t.bar == 3 for t in ts)
    assert all(t.baz == 1 or t.baz == 2 for t in ts)
    assert any(t.baz == 1 for t in ts)
    assert any(t.baz == 2 for t in ts)

## Reproducibility

def test_reproducibility():
    scenario = compileScenic(
        'ego = Object\n'
        'Object offset by 0@3, facing (0, 360) deg\n'
        'Object offset by 0@6, facing (0, 360) deg\n'
        'param foo = Uniform(1, 4, 9, 16, 25, 36)\n'
        'x = (0, 1)\n'
        'require x > 0.8'
    )
    seeds = [random.randint(0, 100000) for i in range(10)]
    for seed in seeds:
        random.seed(seed)
        baseScene, baseIterations = scenario.generate(maxIterations=200)
        for j in range(20):
            random.seed(seed)
            scene, iterations = scenario.generate(maxIterations=200)
            assert len(scene.objects) == len(baseScene.objects)
            for obj, baseObj in zip(scene.objects, baseScene.objects):
                assert obj.heading == baseObj.heading
            assert scene.params['foo'] == baseScene.params['foo']
            assert iterations == baseIterations

## Dependencies and lazy evaluation

def test_shared_dependency():
    scenario = compileScenic(
        'x = (-1, 1)\n'
        'ego = Object at (x * x) @ 0'
    )
    xs = [sampleEgo(scenario).position.x for i in range(60)]
    assert all(0 <= x <= 1 for x in xs)
    assert any(x < 0.25 for x in xs)
    assert any(0.25 < x for x in xs)

def test_shared_dependency_lazy():
    scenario = compileScenic(
        'vf = VectorField("Foo", lambda pos: 2 * pos.x)\n'
        'x = (0, 1) relative to vf\n'
        'ego = Object at 1 @ 0, facing x\n'
        'other = Object at -1 @ 0, facing x'
    )
    for i in range(60):
        scene, iterations = scenario.generate(maxIterations=1)
        egoH = scene.objects[0].heading
        assert 2 <= egoH <= 3
        otherH = scene.objects[1].heading
        assert -2 <= otherH <= -1
        assert (egoH - otherH) == pytest.approx(4)

def test_inside_delayed_argument():
    scenario = lazyTestScenario('Uniform(1.2, x)', offset='Uniform(-1, 1)')
    hs = [sampleEgo(scenario).heading for i in range(140)]
    assert all(h == 1.2 or h == pytest.approx(0) or h == pytest.approx(2) for h in hs)
    assert any(h == 1.2 for h in hs)
    assert any(h == pytest.approx(0) for h in hs)
    assert any(h == pytest.approx(2) for h in hs)
