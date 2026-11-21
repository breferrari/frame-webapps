// web-apps: starts the Web Apps manager (bin/frame-webapp manager) from the folder this program is in.
//
// Why a compiled program: installers such as FramePort add one *program* from an app's folder to Steam, and only
// accept ELF binaries, not scripts. This one finds its own folder and runs
//
//     /usr/bin/python3 <folder>/bin/frame-webapp manager
//
// with FRAME_WEBAPPS_EXTERNAL=1 in the environment, which tells the manager that its Steam entry belongs to whoever
// installed it, so it must not add one of its own.
//
// Freestanding (no libc, raw system calls, aarch64 Linux only), so it has nothing to depend on:
//     gcc -Os -static -nostdlib -ffreestanding -fno-stack-protector -o web-apps launcher/web-apps.c

#define SYS_write 64
#define SYS_readlinkat 78
#define SYS_exit 93
#define SYS_execve 221
#define AT_FDCWD (-100)
#define MAX_ENV 4096

static long syscall4(long number, long a, long b, long c, long d) {
    register long x8 __asm__("x8") = number;
    register long x0 __asm__("x0") = a;
    register long x1 __asm__("x1") = b;
    register long x2 __asm__("x2") = c;
    register long x3 __asm__("x3") = d;
    __asm__ volatile("svc 0" : "+r"(x0) : "r"(x8), "r"(x1), "r"(x2), "r"(x3) : "memory");
    return x0;
}

static unsigned long length(const char *s) {
    unsigned long n = 0;
    while (s[n]) n++;
    return n;
}

static void fail(const char *message) {
    syscall4(SYS_write, 2, (long)message, (long)length(message), 0);
    syscall4(SYS_exit, 127, 0, 0, 0);
}

static char script[4096 + 32];
static char *new_argv[4];
static char *new_env[MAX_ENV + 2];

void start_c(long *stack) {
    long argc = stack[0];
    char **argv = (char **)(stack + 1);
    char **envp = argv + argc + 1;

    long n = syscall4(SYS_readlinkat, AT_FDCWD, (long)"/proc/self/exe", (long)script, 4096);
    if (n <= 0 || n >= 4096) fail("web-apps: can't find my own folder\n");
    while (n > 0 && script[n - 1] != '/') n--;   // keep the folder, with its trailing slash
    const char *rest = "bin/frame-webapp";
    for (unsigned long i = 0; i <= length(rest); i++) script[n + i] = rest[i];

    new_argv[0] = "/usr/bin/python3";
    new_argv[1] = script;
    new_argv[2] = "manager";
    new_argv[3] = 0;

    long count = 0;
    while (envp[count] && count < MAX_ENV) {
        new_env[count] = envp[count];
        count++;
    }
    new_env[count++] = "FRAME_WEBAPPS_EXTERNAL=1";
    new_env[count] = 0;

    syscall4(SYS_execve, (long)new_argv[0], (long)new_argv, (long)new_env, 0);
    fail("web-apps: can't start /usr/bin/python3\n");
}

__asm__(".text\n.global _start\n_start:\n  mov x29, #0\n  mov x0, sp\n  bl start_c\n");
