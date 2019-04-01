
from pywmi import Domain
from pywmi.errors import ParsingFileError
from pywmi.parser import MinizincParser#, SmtlibParser
from tempfile import TemporaryFile

def temporary_file(content):
    f = TemporaryFile(mode='w+')
    f.write(content)
    f.seek(0)
    return f



def test_parse_error():
    content = "this should raise a ParsingFileError"
    tmp = temporary_file(content)
    try:
        # support, weights, domA, domX, queries = MinizincParser.parseAll(tmp.name)
        _ = MinizincParser.parseAll(tmp.name)
        assert False
    except ParsingFileError:
        assert True
    finally:
        #tmp.close()
        pass


