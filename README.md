PAPRIKA TO PDF CONVERTER
========================

A lightweight web application that converts Paprika App recipe exports 
(.paprikarecipes) into a beautifully formatted, printable PDF cookbook.

DESCRIPTION
-----------

This tool accepts a standard Paprika export file (ZIP format), parses the 
internal JSON and images, and renders a typographic HTML layout. It then 
uses WeasyPrint to generate a single PDF document complete with:

 - A custom cover page with the user's name.
 - An automatic Table of Contents.
 - Memory-optimized image handling (auto-resizing) for stability on 
   low-resource hosting environments.

USAGE
-----

The application is containerized and ready for deployment on services like 
Render, Google Cloud Run, or local Docker environments.

1. Build the container:
   $ docker build -t paprika-pdf .

2. Run the application:
   $ docker run -p 5000:5000 paprika-pdf

3. Open your browser at http://localhost:5000

CONFIGURATION
-------------

The application uses the following defaults to ensure stability:
 - Workers: 1 (to prevent memory overflow)
 - Timeout: 120s (for large PDF generation)
 - Image Width: Max 600px (resized automatically)

LICENSE
-------

This project is licensed under the MIT License. You are free to use, 
modify, and distribute this software. See the LICENSE file for details.

Happy Cooking!
