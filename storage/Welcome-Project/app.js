// CodeCloud Sample Application
console.log("Welcome-Project initialized!");

const button = document.getElementById("demoBtn");
const output = document.getElementById("output");

if (button && output) {
  let counter = 0;
  button.addEventListener("click", () => {
    counter++;
    output.innerText = `You clicked the button ${counter} times! Edited live via CodeCloud.`;
  });
}
