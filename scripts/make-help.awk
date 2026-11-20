# Lists the Makefile's targets for `make help`, in the sections the Makefile is
# laid out in, each with the first sentence of the `##` comment above it.
#
# A section is a spaced-out banner, such as `#   B A C K E N D`, together with
# a `# --- … ---` heading under it. Only the targets under such a heading are
# listed, which leaves out file targets such as `$(FRONTEND_MODULES)` and the
# help target itself. Descriptions wrap to fit 80 columns.

BEGIN {
    width = 80
    # The longest target name
    column = 24
    print "Usage: make <target>"
}

# A banner's letters close up into words: "F U L L   S T A C K" is "Full stack"
/^#   [A-Z]( [A-Z]|   [A-Z])*$/ {
    name = substr($0, 5)
    gsub(/   /, "_", name)
    gsub(/ /, "", name)
    gsub(/_/, " ", name)
    component = toupper(substr(name, 1, 1)) tolower(substr(name, 2))
    heading = ""
    next
}

/^# --- / {
    heading = $0
    sub(/^# --- /, "", heading)
    sub(/ -+$/, "", heading)
    shown = 0
    next
}

/^##/ {
    line = $0
    sub(/^## ?/, "", line)
    comment = (comment == "") ? line : (comment " " line)
    next
}

/^[a-z][a-z0-9-]*:/ && heading != "" {
    target = $0
    sub(/:.*/, "", target)
    if (!shown) {
        printf "\n%s: %s\n", component, heading
        shown = 1
    }
    describe(target, first_sentence(comment))
}

# A comment describes only the target right below it
{ comment = "" }

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
