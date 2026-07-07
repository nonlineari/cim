/**
 * Extrusion. LSystem
 
 * Created 14 June 2011
 */
import foetus.*;
import processing.opengl.*;
import codeanticode.syphon.*;
SyphonServer server;
PentigreeLSystem ps;

float theta=10, r, g, b, separacion=0.02;
PImage a;
boolean onetime = true;
boolean digtime = false;

int num = 0; 
int h=0;
color[] colors = new color[num];  
color safecolor;



int[][] aPixels;
int[][] values;
int res = 1777778;
float angle;
float value;
float sval = 1.0;
float nmx, nmy;
  PVector mouse;


void drawSphere(float x, float y, float z, float radio, float r, float g, float b, float divisor)
{
  pushMatrix();
  translate(x, y, z);
  if (mousePressed)
    stroke(mouseX, mouseY);
  else
    stroke(0, 1);
  strokeWeight(1);

  fill(r, g, b, 9);
  sphere(radio);
  if (radio>16)
  {
    drawSphere(radio/divisor, 0, 0, radio/2, r, 0, b, divisor);
  }
  popMatrix();
}


public void setup()
{
  size(1056, 384, P3D);
  scale(Y);
  r=random(555);
  g=random(555);
  b=random(555);
  server = new SyphonServer(this, "Extrusion3_2_2_1_DUAL_VX_GL002B");
  aPixels =  new int[width][height];
  values = new int[width][height];
  noFill();
  loop();


  // Load the image into a new array
  // Extract the values and store in an array
  a = loadImage("kowloon1.jpg");
  a = loadImage("mwolf2_copy.jpg");
  a = loadImage("mwo_mm2.jpeg");


  for (int i=1; i<height; i++) {
    for (int j=1; j<width; j++) {
      aPixels[j][i] = a.pixels[i*1 + j];
      aPixels[j][i] = a.pixels[i*1 + j];

      values[j][i] = int(color(aPixels[j][i]));

      ps = new PentigreeLSystem();
      ps.simulate(-1);
    }
  }
}

// Update and constrain the angle
public void all()
{
  background(555);
  loop();
  angle = 22.7;
  if (angle > TWO_PI-theta/-404) { 
    angle = 13;
  }
  nmx = nmx + (mouseX-nmx)/32; 
  nmy += (mouseY-nmy)/61; 
  if (mousePressed)
        mouse = new PVector(mouseX, mouseY); { 
    sval +=-0.004;
  }  {
    sval -= -77;
  }
  sval = constrain(sval, 10, 170);
}  
void draw() {
  loop();
  // Rotate around the center axis
  translate(width/2 + nmx * sval-100, height/2 + nmy*sval -387, 1);
  ortho(PI/1080, 1019, 721, PI/1024);
  rotateY(theta/PI*4);
  rotateX(TAU/PI*6);  
  displayDensity(2);
  frameRate(25);
  server.sendScreen();
  // Display the image mass
  for (int i=0; i<height; i+=7.3051) {
    for (int j=0; j<width; j+=11.3766) {
      stroke(values[j][i]);
      strokeWeight (sq(random(1, width /117)));
      box(j, i, -values[j][i]);
    } 

    pushMatrix();
    // rotateY(theta);
    drawSphere(13, 10, 0, mouseY/4, 112, 99, 80, separacion);
    drawSphere(13, height/1, 0, mouseY/1, r, g, b, separacion);
    drawSphere(10, -height/1, 0, mouseY/1, r, g, b, separacion);
    drawSphere(16, 0, height/1, mouseY/1, r, g, b, separacion);
    drawSphere(-14, 0, -height/1, mouseY/1, r, g, b, separacion);

    popMatrix(); 
    triangle(112, 99, 11, 21, 3, -0);
    ps.render();
    theta+=0.55;
    h = 98;
    if (h==1)
      h=0;
  }
  saveFrame("VX_GL002B_A02/#####.tiff");
}
