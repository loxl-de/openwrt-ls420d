#!/usr/bin/env python3
"""Native tests run the actual patched converter; only ARM includes shimmed."""
import pathlib, subprocess, sys, tempfile
tree = pathlib.Path(sys.argv[1]).resolve()
temporary = tempfile.TemporaryDirectory(prefix='ls420d-atags-test-')
work = pathlib.Path(temporary.name)
support = r'''
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <assert.h>
#include <libfdt.h>
typedef uint32_t u32;
typedef uint32_t __be32;
typedef uint64_t __be64;
#define COMMAND_LINE_SIZE 1024
#define ATAG_CORE 0x54410001
#define ATAG_MEM 0x54410002
#define ATAG_INITRD2 0x54420005
#define ATAG_CMDLINE 0x54410009
#define ATAG_SERIAL 0x54410006
struct tag_header { uint32_t size, tag; };
struct tag_core { uint32_t flags, pagesize, rootdev; };
struct tag { struct tag_header hdr; union {
    struct { uint32_t size, start; } mem;
    struct { uint32_t start, size; } initrd;
    struct { uint32_t low, high; } serialnr;
    struct { char cmdline[1]; } cmdline;
} u; };
#define tag_size(type) ((sizeof(struct type) + sizeof(struct tag_header)) >> 2)
#define for_each_tag(t,base) for (t=(base); t->hdr.size; t=(void *)((uint32_t *)t+t->hdr.size))
'''
harness = r'''
static void trial(int with_initrd) {
    union { uint64_t align; char bytes[8192]; } storage;
    uint32_t tags[512] = {0}; unsigned n=0;
    void *fdt=storage.bytes; int ch, mem, length;
    const char *cmd="console=bad root=/dev/mtdblock8";
    fdt32_t memory[] = {cpu_to_fdt32(0),cpu_to_fdt32(0x20000000)};
    assert(fdt_create_empty_tree(fdt,sizeof(storage.bytes))==0);
    ch=fdt_add_subnode(fdt,0,"chosen"); assert(ch>=0);
    assert(fdt_setprop_string(fdt,ch,"bootargs","console=ttyS0,115200")==0);
    assert(fdt_setprop_string(fdt,ch,"append-rootblock","root=/dev/mtdblock")==0);
    mem=fdt_add_subnode(fdt,0,"memory"); assert(mem>=0);
    assert(fdt_setprop(fdt,mem,"reg",memory,sizeof(memory))==0);
    tags[n++]=2; tags[n++]=ATAG_CORE;
    unsigned words=(8+strlen(cmd)+1+3)/4;
    tags[n++]=words; tags[n++]=ATAG_CMDLINE;
    memcpy(&tags[n],cmd,strlen(cmd)+1); n+=words-2;
    tags[n++]=4; tags[n++]=ATAG_MEM;
    tags[n++]=0x10000000; tags[n++]=0xdead0000;
    if (with_initrd) {
        tags[n++]=4; tags[n++]=ATAG_INITRD2;
        tags[n++]=0x02600040; tags[n++]=512;
    }
    assert(atags_to_fdt(tags,fdt,sizeof(storage.bytes))==0);
    ch=fdt_path_offset(fdt,"/chosen"); assert(ch>=0);
    const char *bootargs=fdt_getprop(fdt,ch,"bootargs",&length);
    assert(bootargs && strcmp(bootargs,"console=ttyS0,115200 root=/dev/mtdblock8")==0);
    const char *vendor=fdt_getprop(fdt,ch,"bootloader-args",&length);
    assert(vendor && strcmp(vendor,cmd)==0);
    mem=fdt_path_offset(fdt,"/memory"); assert(mem>=0);
    const void *reg=fdt_getprop(fdt,mem,"reg",&length);
    assert(reg && length==sizeof(memory) && !memcmp(reg,memory,sizeof(memory)));
    const fdt32_t *start=fdt_getprop(fdt,ch,"linux,initrd-start",&length);
    if (with_initrd && EXPECT_INITRD) {
        assert(start && length==4 && fdt32_to_cpu(*start)==0x02600040);
        const fdt32_t *end=fdt_getprop(fdt,ch,"linux,initrd-end",&length);
        assert(end && length==4 && fdt32_to_cpu(*end)==0x02600240);
    } else {
        assert(!start);
        assert(!fdt_getprop(fdt,ch,"linux,initrd-end",&length));
    }
}
int main(void) {
    trial(0); trial(1);
    puts("PASS: absent/present INITRD2; filtered command line and DT memory preserved");
    return 0;
}
'''
for name, source, expected in (
    ('after', tree/'arch/arm/boot/compressed/atags_to_fdt.c', 1),
):
    code='\n'.join(line for line in source.read_text().splitlines() if not line.startswith('#include'))
    generated=work/(name+'.c')
    generated.write_text(support+'\n'+code+'\n'+harness)
    lib=tree/'scripts/dtc/libfdt'
    objects=[lib/(f+'.c') for f in ('fdt','fdt_ro','fdt_rw','fdt_wip','fdt_sw','fdt_empty_tree','fdt_strerror')]
    binary=work/name
    subprocess.run(['gcc','-std=gnu11','-O2','-Wall','-Wextra','-Wno-pointer-to-int-cast',
        '-DCONFIG_ARM_ATAG_DTB_COMPAT_CMDLINE_MANGLE',f'-DEXPECT_INITRD={expected}',
        '-I'+str(lib),str(generated),*map(str,objects),'-o',str(binary)],check=True)
    print(name,flush=True)
    subprocess.run([str(binary)],check=True)
