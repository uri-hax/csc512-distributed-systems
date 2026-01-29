#include <stdint.h>
#include <stdbool.h>
#include <unistd.h>

// This code is very bad but I don't have time to fix it. I should be using a lookup
// table to drive the state machine instead of these ugly conditionals.

#define STATE_WORD 0
#define STATE_SPACE 1

int main(const int argc, const char* const argv[]) {
	// Start in a word.
	// TODO: this is invalid.
	bool state = STATE_WORD;

	// Set up buffer to read data into.
	int bytes = 0;
	uint8_t buf[4096];

	// Set up buffer for formatted output.
	int o_bytes = 0;
	uint8_t o_buf[4096];

	// Read the data.
	while ((bytes = read(0, buf, sizeof(buf) / sizeof(buf[0]))) > 0) {
		o_bytes = 0;
		for (int i = 0; i < bytes; ++i) {

			// If we are in space, ignore spaces and transition on characters.
			if (state == STATE_SPACE) {
				if (buf[i] != ' ') {
					o_buf[o_bytes] = buf[i];
					o_bytes += 1;
					state = STATE_WORD;
				}

			// If we are not in a space, transition on spaces.
			} else {
				if(buf[i] == ' ') {
					state = STATE_SPACE;
					o_buf[o_bytes] = '\n';
				} else {
					o_buf[o_bytes] = buf[i];
				}
				o_bytes += 1;
			}
		}

		// Write the output.
		write(1, o_buf, o_bytes);
	}

	// Exit cleanly.
	return 0;
}
