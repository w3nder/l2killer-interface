// PE entry wrapper. Import resolution loads C4Bars.dll normally before this
// code runs. Preserve the original CRT/DllMain result and all stdcall arguments.
// No absolute addresses: module base comes from hInstance, so rebasing works.
    .text
    .globl _C4Entry
_C4Entry:
    pushl %ebp
    movl %esp, %ebp
    pushl %ebx
    pushl %esi
    movl 8(%ebp), %ebx
    pushl 16(%ebp)
    pushl 12(%ebp)
    pushl 8(%ebp)
    leal ORIGINAL_ENTRY_RVA(%ebx), %eax
    call *%eax
    movl %eax, %esi
    cmpl $1, 12(%ebp)
    jne done
    testl %esi, %esi
    je done
    pushl %ebx
    call *INIT_IAT_RVA(%ebx)
    addl $4, %esp
done:
    movl %esi, %eax
    popl %esi
    popl %ebx
    leave
    ret $12
