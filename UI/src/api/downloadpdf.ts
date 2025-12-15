import { marked } from "marked";
// import html2pdf from "html2pdf";
declare const html2pdf: any;

export function downloadPdf(markdown: string, fileName = "file.pdf") {
  // Convert markdown → HTML
  console.log(markdown)
  const htmlContent = marked(markdown, { breaks: true });

  // Full HTML wrapper with styles (Cloudscape style)
  const html = `
    <html>
      <head>
        <style>
          body {
            font-family: "Open Sans", Arial, sans-serif;
            padding: 20px;
            font-size: 14px;
            line-height: 1.6;
            color: #1a202c;
          }

          h1 { font-size: 26px; font-weight: 600; }
          h2 { font-size: 22px; font-weight: 600; }
          h3 {
            font-size: 18px;
            font-weight: 600;
            border-left: 4px solid #0073bb;
            padding-left: 8px;
            margin-top: 20px;
          }

          p { margin: 10px 0; }

          table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
          }

          th {
            background: #eaeded;
            padding: 8px;
            border: 1px solid #d5dbdb;
            font-weight: 600;
          }

          td {
            padding: 8px;
            border: 1px solid #d5dbdb;
          }

          tr:nth-child(even) {
            background: #f7fafa;
          }

          strong { font-weight: 700; }
          em { font-style: italic; }

          code, pre {
            background: #f4f4f4;
            padding: 6px;
            border-radius: 4px;
            font-family: monospace;
          }

          .cloudscape-box {
            border: 1px solid #d5dbdb;
            border-radius: 8px;
            padding: 16px;
            background: #ffffff;
            margin-top: 20px;
          }
        </style>
      </head>
      <body>
      <div style="padding: 8px; background: white;">
        <div class="cloudscape-box">${htmlContent}</div>
        </div>
      </body>
    </html>
  `;

  const options = {
          margin: 0.5,
          filename: `${fileName}.pdf`,
          image: { type: "jpeg", quality: 0.98 },
          html2canvas: {
            scale: 2,
            useCORS: true,
            scrollY: 0,
          },
          jsPDF: { unit: "in", format: "a4", orientation: "portrait" },
        };
  

  html2pdf().from(html).set(options).save();
}
