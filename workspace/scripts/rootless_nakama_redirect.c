#define _GNU_SOURCE
#include <arpa/inet.h>
#include <dlfcn.h>
#include <netinet/in.h>
#include <sys/socket.h>

/*
 * The published Wildfire Unity build has Nakama's rootful-Docker bridge IP
 * embedded in its assets. Rootless Docker exposes Nakama on 127.0.0.1
 * instead, so redirect only that IPv4 destination at connect(2) time.
 */
int connect(int fd, const struct sockaddr *address, socklen_t length) {
    static int (*real_connect)(int, const struct sockaddr *, socklen_t);
    if (!real_connect) {
        real_connect = dlsym(RTLD_NEXT, "connect");
    }

    if (address && address->sa_family == AF_INET &&
        length >= sizeof(struct sockaddr_in)) {
        const struct sockaddr_in *source = (const struct sockaddr_in *)address;
        struct in_addr embedded;
        inet_pton(AF_INET, "172.23.0.50", &embedded);
        if (source->sin_addr.s_addr == embedded.s_addr) {
            struct sockaddr_in redirected = *source;
            inet_pton(AF_INET, "127.0.0.1", &redirected.sin_addr);
            return real_connect(fd, (const struct sockaddr *)&redirected,
                                sizeof(redirected));
        }
    }
    if (address && address->sa_family == AF_INET6 &&
        length >= sizeof(struct sockaddr_in6)) {
        const struct sockaddr_in6 *source =
            (const struct sockaddr_in6 *)address;
        struct in_addr embedded;
        inet_pton(AF_INET, "172.23.0.50", &embedded);
        if (IN6_IS_ADDR_V4MAPPED(&source->sin6_addr) &&
            __builtin_memcmp(&source->sin6_addr.s6_addr[12], &embedded,
                             sizeof(embedded)) == 0) {
            struct sockaddr_in6 redirected = *source;
            inet_pton(AF_INET6, "::ffff:127.0.0.1", &redirected.sin6_addr);
            return real_connect(fd, (const struct sockaddr *)&redirected,
                                sizeof(redirected));
        }
    }
    return real_connect(fd, address, length);
}
