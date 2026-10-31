-- Exports a .pptx to PDF through Keynote: osascript export_pdf.applescript <in.pptx> <out.pdf>
on run argv
  set inFile to POSIX file (item 1 of argv)
  set outFile to POSIX file (item 2 of argv)
  tell application "Keynote"
    set theDoc to open inFile
    delay 1
    export theDoc to outFile as PDF with properties {PDF image quality:Best}
    close theDoc saving no
  end tell
end run
