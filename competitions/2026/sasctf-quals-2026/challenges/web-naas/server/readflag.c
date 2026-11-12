#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char *argv[]) {
    if (argc != 2 || strcmp(argv[1], "please") != 0) {
        fprintf(stderr, "Usage: %s please\n", argv[0]);
        return 1;
    }

    FILE *file = fopen("/flag.txt", "r");
    if (file == NULL) {
        perror("failed to open file");
        return 1;
    }

    char buffer[256];
    while (fgets(buffer, sizeof(buffer), file) != NULL) {
        fputs(buffer, stdout);
    }

    fclose(file);
    return 0;
}