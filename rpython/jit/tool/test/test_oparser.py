import py
import sys
from rpython.rtyper.lltypesystem import lltype, llmemory

from rpython.jit.tool.oparser import parse, OpParser
from rpython.jit.metainterp.resoperation import rop
from rpython.jit.metainterp.history import AbstractDescr, JitCellToken,\
     TargetToken

class BaseTestOparser(object):

    OpParser = None

    def parse(self, *args, **kwds):
        kwds['OpParser'] = self.OpParser
        return parse(*args, **kwds)

    def test_basic_parse(self):
        x = """
        [i0, i1]
        # a comment
        i2 = int_add(i0, i1)
        i3 = int_sub(i2, 3) # another comment
        finish() # (tricky)
        """
        loop = self.parse(x)
        assert len(loop.operations) == 3
        assert [op.getopnum() for op in loop.operations] == [rop.INT_ADD, rop.INT_SUB,
                                                        rop.FINISH]
        assert len(loop.inputargs) == 2
        assert loop.operations[-1].getdescr()

    def test_const_ptr_subops(self):
        x = """
        [p0]
        guard_class(p0, ConstClass(vtable)) []
        """
        S = lltype.Struct('S')
        vtable = lltype.nullptr(S)
        loop = self.parse(x, None, locals())
        assert len(loop.operations) == 1
        assert loop.operations[0].getdescr()
        assert loop.operations[0].getfailargs() == []

    def test_descr(self):
        class Xyz(AbstractDescr):
            I_am_a_descr = True # for the mock case

        x = """
        [p0]
        i1 = getfield_gc_i(p0, descr=stuff)
        """
        stuff = Xyz()
        loop = self.parse(x, None, locals())
        assert loop.operations[0].getdescr() is stuff

    def test_after_fail(self):
        x = """
        [i0]
        guard_value(i0, 3) []
        i1 = int_add(1, 2)
        """
        loop = self.parse(x, None, {})
        assert len(loop.operations) == 2

    def test_descr_setfield(self):
        class Xyz(AbstractDescr):
            I_am_a_descr = True # for the mock case

        x = """
        [p0]
        setfield_gc(p0, 3, descr=stuff)
        """
        stuff = Xyz()
        loop = self.parse(x, None, locals())
        assert loop.operations[0].getdescr() is stuff

    def test_getvar_const_ptr(self):
        x = '''
        []
        call_n(ConstPtr(func_ptr))
        '''
        TP = lltype.GcArray(lltype.Signed)
        NULL = lltype.cast_opaque_ptr(llmemory.GCREF, lltype.nullptr(TP))
        loop = self.parse(x, None, {'func_ptr' : NULL})
        assert loop.operations[0].getarg(0).value == NULL

    def test_jump_target(self):
        x = '''
        []
        jump()
        '''
        loop = self.parse(x)
        assert loop.operations[0].getdescr() is loop.original_jitcell_token

    def test_jump_target_other(self):
        looptoken = JitCellToken()
        looptoken.I_am_a_descr = True # for the mock case
        x = '''
        []
        jump(descr=looptoken)
        '''
        loop = self.parse(x, namespace=locals())
        assert loop.operations[0].getdescr() is looptoken

    def test_floats(self):
        x = '''
        [f0]
        f1 = float_add(f0, 3.5)
        '''
        loop = self.parse(x)
        box = loop.operations[0].getarg(0)
        # we cannot use isinstance, because in case of mock the class will be
        # constructed on the fly
        assert box.__class__.__name__ == 'InputArgFloat'

    def test_debug_merge_point(self):
        x = '''
        []
        debug_merge_point(0, 0, "info")
        debug_merge_point(0, 0, 'info')
        debug_merge_point(1, 1, '<some ('other.')> info')
        debug_merge_point(0, 0, '(stuff) #1')
        '''
        loop = self.parse(x)
        assert loop.operations[0].getarg(2)._get_str() == 'info'
        assert loop.operations[0].getarg(1).value == 0
        assert loop.operations[1].getarg(2)._get_str() == 'info'
        assert loop.operations[2].getarg(2)._get_str() == "<some ('other.')> info"
        assert loop.operations[2].getarg(1).value == 1
        assert loop.operations[3].getarg(2)._get_str() == "(stuff) #1"


    def test_descr_with_obj_print(self):
        x = '''
        [p0]
        setfield_gc(p0, 1, descr=<SomeDescr>)
        '''
        loop = self.parse(x)
        # assert did not explode

    example_loop_log = '''\
    # bridge out of Guard12, 6 ops
    [i0, i1, i2]
    i4 = int_add(i0, 2)
    i6 = int_sub(i1, 1)
    i8 = int_gt(i6, 3)
    guard_true(i8, descr=<Guard15>) [i4, i6]
    debug_merge_point('(no jitdriver.get_printable_location!)', 0)
    jump(i6, i4, descr=<Loop0>)
    '''

    def test_parse_no_namespace(self):
        loop = self.parse(self.example_loop_log, no_namespace=True)

    def test_attach_comment_to_loop(self):
        loop = self.parse(self.example_loop_log, no_namespace=True)
        assert loop.comment == '    # bridge out of Guard12, 6 ops'

    def test_parse_new_with_comma(self):
        # this is generated by PYPYJITLOG, check that we can handle it
        x = '''
        []
        p0 = new(, descr=<SizeDescr 12>)
        '''
        loop = self.parse(x)
        assert loop.operations[0].getopname() == 'new'

    def test_no_fail_args(self):
        x = '''
        [i0]
        guard_true(i0, descr=<Guard0>)
        '''
        loop = self.parse(x, nonstrict=True)
        assert loop.operations[0].getfailargs() == []

    def test_offsets(self):
        x = """
        [i0, i1]
        +10: i2 = int_add(i0, i1)
        i3 = int_add(i2, 3)
        """
        #    +30: --end of the loop--
        loop = self.parse(x)
        assert loop.operations[0].offset == 10
        assert not hasattr(loop.operations[1], 'offset')

    def test_last_offset(self):
        x = """
        [i0, i1]
        +10: i2 = int_add(i0, i1)
        i3 = int_add(i2, 3)
        +30: --end of the loop--
        """
        loop = self.parse(x)
        assert len(loop.operations) == 2
        assert loop.last_offset == 30


class TestOpParser(BaseTestOparser):

    OpParser = OpParser

    def test_label(self):
        x = """
        [i0]
        label(i0, descr=1)
        jump(i0, descr=1)
        """
        loop = self.parse(x)
        assert loop.operations[0].getdescr() is loop.operations[1].getdescr()
        assert isinstance(loop.operations[0].getdescr(), TargetToken)


class ForbiddenModule(object):
    def __init__(self, name, old_mod):
        self.name = name
        self.old_mod = old_mod

    def __getattr__(self, attr):
        assert False, "You should not import module %s" % self.name


class TestOpParserWithMock(BaseTestOparser):

    class OpParser(OpParser):
        use_mock_model = True

    def setup_class(cls):
        forbidden_mods = [
            'rpython.jit.metainterp.history',
            'rpython.rtyper.lltypesystem.lltype',
            ]
        for modname in forbidden_mods:
            if modname in sys.modules:
                newmod = ForbiddenModule(modname, sys.modules[modname])
                sys.modules[modname] = newmod

    def teardown_class(cls):
        for modname, mod in sys.modules.items():
            if isinstance(mod, ForbiddenModule):
                sys.modules[modname] = mod.old_mod
