from collections import namedtuple

def get_object_bql_result(ret):
    rtypes, rvalues = ret
    ret = []
    keys = []
    for k in rtypes:
        keys.append(k[0])
    for v in rvalues:
        d = {}
        i = 0
        for vv in v:
            # 只对数字和None转字符串，保留dict等复杂类型
            if vv is None or isinstance(vv, (int, float)) and not isinstance(vv, bool):
                vv = str(vv)
            d[keys[i]] = vv
            i += 1
        t = namedtuple('Struct', keys)(**d)
        ret.append(t)
    return ret
