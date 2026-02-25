
// take stdin as input and write it to stdout. If a file is provided as an argument, write the input to the file as well.
use std::env;
use std::fs::File;
use std::io::{self, BufRead, BufReader, Write};

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut file = if args.len() > 1 {
        File::create(&args[1]).ok()
    } else {
        None
    };
    let stdin = io::stdin();
    let reader = BufReader::new(stdin.lock());

    let stdout = io::stdout();
    let mut handle = stdout.lock();

    for line in reader.lines() {
        let line = line.unwrap();
        writeln!(handle, "{}", line).unwrap();
        if let Some(ref mut file) = file {
            writeln!(file, "{}", line).unwrap();
        }
    }
}
