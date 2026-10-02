from scripts.mutation_harness import (
    apply_mutation,
    classify_pytest_result,
    gen_mutants,
)


def test_mutations_are_position_specific_and_exclude_comments_and_strings():
    source = (
        "if left <= right and enabled:\n"
        "    return 64 + 64  # 64\n"
        "    value = 'True == 1'\n"
    )

    mutants = list(gen_mutants(source))
    numeric_mutants = [mutant for mutant in mutants if mutant[2] == "numeric_plus1"]
    assert len(numeric_mutants) == 2
    assert numeric_mutants[0][1] != numeric_mutants[1][1]

    line_number, column, operator, original, mutated = numeric_mutants[1]
    result = apply_mutation(source, line_number, column, operator, original, mutated)

    assert "64 + 65  # 64" in result
    assert "True == 1" in result


def test_mutation_outcomes_do_not_count_test_errors_as_killed():
    killed = (
        '<testsuite tests="1" failures="1" errors="0">'
        '<testcase name="assertion"><failure /></testcase></testsuite>'
    )
    errored = (
        '<testsuite tests="1" failures="0" errors="1">'
        '<testcase name="collection"><error /></testcase></testsuite>'
    )
    passed = (
        '<testsuite tests="1" failures="0" errors="0">'
        '<testcase name="assertion" /></testsuite>'
    )

    assert classify_pytest_result(1, killed) == "killed"
    assert classify_pytest_result(1, errored) == "error"
    assert classify_pytest_result(0, passed) == "survived"
    assert classify_pytest_result(1, "not junit") == "error"
