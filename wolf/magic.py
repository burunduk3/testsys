
def magic_parse( s, v ):
    result = ''
    variable = ''
    cutting = ''
    def mp_normal( x ):
        nonlocal result
        if x == '$':
            return mp_variable_start
        else:
            result += x
            return mp_normal
    def mp_variable_start( x ):
        nonlocal variable
        variable = ''
        if x == '{':
            return mp_complex
        else:
            return mp_variable(x)
    def mp_variable( x ):
        nonlocal variable, result
        if 'a' <= x <= 'z' or 'A' <= x <= 'Z' or '0' <= x <= '9' or x == '_':
            variable += x
            return mp_variable
        else:
            result += v[variable]
            return mp_normal(x)
    def mp_complex( x ):
        nonlocal variable
        if 'a' <= x <= 'z' or 'A' <= x <= 'Z' or '0' <= x <= '9' or x == '_':
            variable += x
            return mp_complex
        else:
            variable = v[variable]
            return mp_modify(x)
    def mp_modify( x ):
        nonlocal result, variable, cutting
        if x == '}':
            result += variable
            return mp_normal
        elif x == '%':
            cutting = ''
            return mp_cutend
        else:
            return mp_modify
    def mp_skipcut( x ):
        return mp_modify(x) if x in {'}', '%', '#'} else mp_skipcut
    def mp_cutend( x ):
        nonlocal variable, cutting
        if x in {'}', '%', '#', '|'}:
            if variable.endswith(cutting):
                variable = variable[:-len(cutting)]
                return mp_skipcut(x)
            return mp_modify(x if x != '|' else '%')
        else:
            cutting += x
            return mp_cutend

    state = mp_normal
    for x in s:
        state = state(x)
    if state is mp_variable:
        result += v[variable]
    return result

