#define _GNU_SOURCE

#include <errno.h>
#include <poll.h>
#include <seccomp.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <unistd.h>

#include <linux/sched.h>
#include <linux/seccomp.h>

static volatile sig_atomic_t forward_signal = 0;

static void die(const char *msg, int rc) {
    if (rc < 0) {
        errno = -rc;
    }
    perror(msg);
    exit(1);
}

static void signal_handler(int sig) {
    forward_signal = sig;
}

static void install_signal_handlers(void) {
    struct sigaction sa;

    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = signal_handler;
    sigemptyset(&sa.sa_mask);

    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGHUP, &sa, NULL);
    sigaction(SIGQUIT, &sa, NULL);
    sigaction(SIGUSR1, &sa, NULL);
    sigaction(SIGUSR2, &sa, NULL);
}

static void send_fd(int sock, int fd) {
    struct msghdr msg;
    struct iovec io;
    char cmsgbuf[CMSG_SPACE(sizeof(fd))];
    struct cmsghdr *cmsg;
    char data = 'F';

    memset(&msg, 0, sizeof(msg));
    memset(cmsgbuf, 0, sizeof(cmsgbuf));

    io.iov_base = &data;
    io.iov_len = sizeof(data);
    msg.msg_iov = &io;
    msg.msg_iovlen = 1;
    msg.msg_control = cmsgbuf;
    msg.msg_controllen = sizeof(cmsgbuf);

    cmsg = CMSG_FIRSTHDR(&msg);
    cmsg->cmsg_level = SOL_SOCKET;
    cmsg->cmsg_type = SCM_RIGHTS;
    cmsg->cmsg_len = CMSG_LEN(sizeof(fd));
    memcpy(CMSG_DATA(cmsg), &fd, sizeof(fd));

    if (sendmsg(sock, &msg, 0) < 0) {
        die("sendmsg", -errno);
    }
}

static int recv_fd(int sock) {
    struct msghdr msg;
    struct iovec io;
    char cmsgbuf[CMSG_SPACE(sizeof(int))];
    struct cmsghdr *cmsg;
    char data;
    int fd;

    memset(&msg, 0, sizeof(msg));
    memset(cmsgbuf, 0, sizeof(cmsgbuf));

    io.iov_base = &data;
    io.iov_len = sizeof(data);
    msg.msg_iov = &io;
    msg.msg_iovlen = 1;
    msg.msg_control = cmsgbuf;
    msg.msg_controllen = sizeof(cmsgbuf);

    if (recvmsg(sock, &msg, 0) < 0) {
        die("recvmsg", -errno);
    }

    cmsg = CMSG_FIRSTHDR(&msg);
    if (cmsg == NULL || cmsg->cmsg_level != SOL_SOCKET || cmsg->cmsg_type != SCM_RIGHTS) {
        fprintf(stderr, "recvmsg: missing listener fd\n");
        exit(1);
    }

    memcpy(&fd, CMSG_DATA(cmsg), sizeof(fd));
    return fd;
}

static int install_filter(void) {
    scmp_filter_ctx ctx;
    int rc;
    int notify_fd;

    ctx = seccomp_init(SCMP_ACT_ALLOW);
    if (ctx == NULL) {
        die("seccomp_init", -errno);
    }

    rc = seccomp_rule_add(ctx, SCMP_ACT_NOTIFY, SCMP_SYS(fork), 0);
    if (rc != 0) {
        die("seccomp_rule_add(fork)", rc);
    }

    rc = seccomp_rule_add(ctx, SCMP_ACT_NOTIFY, SCMP_SYS(vfork), 0);
    if (rc != 0) {
        die("seccomp_rule_add(vfork)", rc);
    }

    rc = seccomp_rule_add(
        ctx,
        SCMP_ACT_NOTIFY,
        SCMP_SYS(clone),
        1,
        SCMP_A0(SCMP_CMP_MASKED_EQ, CLONE_THREAD, 0)
    );
    if (rc != 0) {
        die("seccomp_rule_add(clone)", rc);
    }

    rc = seccomp_rule_add(ctx, SCMP_ACT_NOTIFY, SCMP_SYS(clone3), 0);
    if (rc != 0) {
        die("seccomp_rule_add(clone3)", rc);
    }

    rc = seccomp_load(ctx);
    if (rc != 0) {
        die("seccomp_load", rc);
    }

    notify_fd = seccomp_notify_fd(ctx);
    if (notify_fd < 0) {
        die("seccomp_notify_fd", -errno);
    }

    seccomp_release(ctx);
    return notify_fd;
}

static void respond_continue(int notify_fd, struct seccomp_notif *req, struct seccomp_notif_resp *resp) {
    memset(resp, 0, sizeof(*resp));
    resp->id = req->id;
    resp->flags = SECCOMP_USER_NOTIF_FLAG_CONTINUE;
    if (seccomp_notify_respond(notify_fd, resp) != 0) {
        die("seccomp_notify_respond(CONTINUE)", -errno);
    }
}

static void respond_deny(int notify_fd, struct seccomp_notif *req, struct seccomp_notif_resp *resp) {
    memset(resp, 0, sizeof(*resp));
    resp->id = req->id;
    resp->val = -1;
    resp->error = EPERM;
    if (seccomp_notify_respond(notify_fd, resp) != 0) {
        die("seccomp_notify_respond(EPERM)", -errno);
    }
}

static void supervise_notifications(int notify_fd, pid_t child_pid) {
    struct seccomp_notif *req = NULL;
    struct seccomp_notif_resp *resp = NULL;
    struct pollfd pfd;
    bool startup_clone_allowed = false;
    int rc;

    rc = seccomp_notify_alloc(&req, &resp);
    if (rc != 0) {
        die("seccomp_notify_alloc", rc);
    }

    pfd.fd = notify_fd;
    pfd.events = POLLIN;

    for (;;) {
        int status;
        pid_t waited;

        waited = waitpid(child_pid, &status, WNOHANG);
        if (waited == child_pid) {
            seccomp_notify_free(req, resp);
            if (WIFEXITED(status)) {
                exit(WEXITSTATUS(status));
            }
            if (WIFSIGNALED(status)) {
                raise(WTERMSIG(status));
                exit(128 + WTERMSIG(status));
            }
            exit(1);
        }

        if (forward_signal != 0) {
            kill(child_pid, forward_signal);
            forward_signal = 0;
        }

        rc = poll(&pfd, 1, 250);
        if (rc < 0) {
            if (errno == EINTR) {
                continue;
            }
            die("poll", -errno);
        }
        if (rc == 0) {
            continue;
        }
        if ((pfd.revents & POLLIN) == 0) {
            continue;
        }

        rc = seccomp_notify_receive(notify_fd, req);
        if (rc != 0) {
            if (errno == EINTR || errno == ENOENT || errno == EINVAL) {
                continue;
            }
            die("seccomp_notify_receive", -errno);
        }

        if (!startup_clone_allowed &&
            req->data.nr == __NR_clone &&
            req->data.args[0] == SIGCHLD) {
            startup_clone_allowed = true;
            respond_continue(notify_fd, req, resp);
            continue;
        }

        respond_deny(notify_fd, req, resp);
    }
}

int main(int argc, char **argv) {
    int socks[2];
    pid_t child_pid;

    if (argc < 2) {
        fprintf(stderr, "usage: %s <program> [args...]\n", argv[0]);
        return 1;
    }

    install_signal_handlers();

    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, socks) != 0) {
        die("socketpair", -errno);
    }

    child_pid = fork();
    if (child_pid < 0) {
        die("fork", -errno);
    }

    if (child_pid == 0) {
        int notify_fd;

        close(socks[0]);

        if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) {
            die("prctl(PR_SET_NO_NEW_PRIVS)", -errno);
        }

        notify_fd = install_filter();
        send_fd(socks[1], notify_fd);
        close(notify_fd);
        close(socks[1]);

        execvp(argv[1], &argv[1]);
        die("execvp", -errno);
    }

    close(socks[1]);
    supervise_notifications(recv_fd(socks[0]), child_pid);
    return 0;
}
