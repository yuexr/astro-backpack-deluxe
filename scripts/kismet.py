"""Byte counts for the Blueprint instructions we emit."""


def op_type(x):
    return x["$type"].split(".")[-1].split(",")[0]


def kismet_size(x):
    t = op_type(x)
    if t in [
        "EX_True",
        "EX_False",
        "EX_Self",
        "EX_IntZero",
        "EX_Nothing",
        "EX_EndOfScript",
    ]:
        return 1
    if t in ["EX_InstanceVariable", "EX_LocalVariable", "EX_ObjectConst"]:
        return 9
    if t == "EX_FloatConst":
        return 5
    if t == "EX_StringConst":
        return len(x["Value"].encode("ascii")) + 2
    if t in ["EX_FinalFunction", "EX_LocalFinalFunction", "EX_CallMath"]:
        return 10 + sum(map(kismet_size, x["Parameters"]))
    if t == "EX_Context":
        assert x["Offset"] == kismet_size(x["ContextExpression"])
        return (
            13
            + kismet_size(x["ObjectExpression"])
            + kismet_size(x["ContextExpression"])
        )
    if t == "EX_LetBool":
        return (
            1
            + kismet_size(x["VariableExpression"])
            + kismet_size(x["AssignmentExpression"])
        )
    if t == "EX_JumpIfNot":
        return 5 + kismet_size(x["BooleanExpression"])
    if t == "EX_Return":
        return 1 + kismet_size(x["ReturnExpression"])
    raise ValueError(t)
