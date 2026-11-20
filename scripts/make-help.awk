# Lists the Makefile's targets for `make help`, under the headings the Makefile
# groups them by, each with the first sentence of the `##` comment above it.
#
# A heading is a `# --- … ---` line. A target is listed only when a `##`
# comment sits right above it, which leaves out the help target and file
# targets such as `$(FRONTEND_MODULES)`. Descriptions wrap to fit 80 columns,
# beside a column as wide as the longest target's name.

BEGIN {
    width = 80
}

/^# --- / {
    heading = $0
    sub(/^# --- /, "", heading)
    sub(/ -+$/, "", heading)
    next
}

/^##/ {
    line = $0
    sub(/^## ?/, "", line)
    comment = (comment == "") ? line : (comment " " line)
    next
}

/^[a-z][a-z0-9-]*:/ && comment != "" {
    target = $0
    sub(/:.*/, "", target)
    count++
    targets[count] = target
    headings[count] = heading
    texts[count] = first_sentence(comment)
    if (length(target) > column) column = length(target)
}

# A comment describes only the target right below it
{ comment = "" }

END {
    print "Usage: make <target>"
    for (i = 1; i <= count; i++) {
        if (i == 1 || headings[i] != headings[i - 1]) printf "\n%s:\n", headings[i]
        describe(targets[i], texts[i])
    }
}

# Without its closing period, as some comments have one and others don't
function first_sentence(text,    end) {
    end = index(text, ". ")
    if (end) text = substr(text, 1, end)
    sub(/\.$/, "", text)
    return text
}

# Prints a target beside its description, which wraps within the space the
# target's column leaves
function describe(target, text,    words, count, i, line) {
    count = split(text, words, " ")
    line = ""
    for (i = 1; i <= count; i++) {
        if (line != "" && length(line) + 1 + length(words[i]) > width - column - 4) {
            printf "  %-" column "s  %s\n", target, line
            target = ""
            line = words[i]
        } else {
            line = (line == "") ? words[i] : (line " " words[i])
        }
    }
    printf "  %-" column "s  %s\n", target, line
}
