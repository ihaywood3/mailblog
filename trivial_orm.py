import sqlite3
from zope.interface import Interface,implementer

class IClause:
    def value(self, pg):
        """
        the RHS
        """

class IOperator:
    def __init__(self, v):
        self._value = v

    
    def value(self):
        """
        the RHS
        """
        return self._value

    def operator(pg):
        """
        the operator
        """


class now(IClause):
    def value(self, pg):
        if pg:
            return "now()"
        else:
            return "datetime('now')"


class join(IClause):
    def __init__(self, v):
        self._value = v

    def value(self, pg):
        return self._value


class like(IOperator):
    
    def operator(self, pg):
        if pg:
            return "ilike"
        else:
            return "like"

class gt(IOperator):
    
    def operator(self, pg):
        return ">"

class lt(IOperator):
    
    def operator(self, pg):
        return "<"

class gte(IOperator):
    
    def operator(self, pg):
        return "=>"

class lte(IOperator):
    
    def operator(self, pg):
        return "<="

    
def make_insert(tbl, data, pg):
    k = list(data.keys())
    i1 = ",".join(k)
    i2 = []
    v = []
    if pg:
        param="%s"
    else:
        param="?"
    for i in k:
        if isinstance(data[i], IClause):
            i2.append(data[i].value(pg))
        else:
            v.append(data[i])
            i2.append(param)
    return ("insert into %s (%s) values (%s)" % (tbl,i1,",".join(i2)),tuple(v))

def make_query(query, pg):
    if pg:
        param="%s"
    else:
        param="?"
    vals = []
    q =[]
    for k,v in query.items():
        if isinstance(v,IOperator):
            op = v.operator(pg)
            v = v.value()
        else:
            op = "="
        if isinstance(v, IClause):
            v = v.value(pg)
        else:
            vals.append(v)
            v = param
        q.append("%s %s %s" % (k, op, v))
    return (" and ".join(q),vals)

def make_update(tbl, data, query, pg):
    if pg:
        param="%s"
    else:
        param="?"
    vals = []
    u1 = []
    for k, v in data:
        if isinstance(v, IClause):
            u1.append("%s=%s" % (k,v.value(p)))
        else:
            vals.append(v)
            u1.append("%s=%s" % (k,param))
    u2, vals2 = make_query(query, pg)
    return ("update %s set %s where %s" % (tbl, u1, u2),tuple(vals+vals2))

def make_delete(tbl, query, pg):
    d1, vals = make_query(query, pg)
    return ("delete from %s where %s" % (tbl, d1),tuple(vals))

def make_select(cols, tbl, query, pg):
    if type(cols) is list:
        cols = ",".join(cols)
    if type(tbl) is list:
        tbl = ",".join(tbl)
    s1, vals = make_query(query, pg)
    return ("select %s from %s where %s" % (cols, tbl, s1),tuple(vals))


class SqliteWrapper:
    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        self.db.row_factory = sqlite3.Row

    def insert(self, tbl, **data):
        return self.db.execute(*make_insert(tbl, data, False))

    def update(self, tbl, data, **query):
        return self.db.execute(*make_update(tbl, data, query, False))

    def delete(self, tbl, **query):
        return self.db.execute(*make_delete(tbl, query, False))

    def select(self, tbl, cols="*", **query):
        return self.db.execute(*make_select(cols, tbl, query, False))





