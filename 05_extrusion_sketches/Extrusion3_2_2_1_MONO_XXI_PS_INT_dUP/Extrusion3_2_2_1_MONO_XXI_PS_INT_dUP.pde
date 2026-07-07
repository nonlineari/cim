/**
 * Extrusion. LSystem — RAND SYSTEM B (dUP / cloud collision)
 * CIM generation — conversation entity archive
 */
import foetus.*;
import processing.opengl.*;
import processing.sound.*;
import spout.*;
Spout spout;
LSystem ps;
FFT fft;
AudioIn in;
int bands = 512;
float[] spectrum = new float[bands];
float theta=10, r, g, b, separacion=0.02;
PImage a;
boolean onetime = true;
boolean digtime = false;
boolean rampup = true;
String sendername;

int num = 0;
int h=0;
color[] colors = new color[num];
color safecolor;

int[][] aPixels;
int[][] values;
int res = 50000;
float angle;
float value;
float sval = 1.0;
float nmx, nmy;

void drawSphere(float x, float y, float z, float radio, float r, float g, float b, float divisor)
{
  pushMatrix();
  translate(x, y, radio);
  if (mousePressed) stroke(141, 9);
  else stroke(0, 1);
  strokeWeight(1);
  fill(r, g, b, 15);
  box(radio);
  if (z>16) drawSphere(radio/divisor, 0, 0, radio/2, r, 0, b, divisor);
  popMatrix();
}

public void setup()
{
  size(1024, 768, P3D);
  scale(sval);
  r=random(000);
  g=random(070);
  b=random(120);
  background(000);
  fft = new FFT(this, bands);
  in = new AudioIn(this, 0);
  in.start();
  fft.input(in);
  aPixels =  new int[width][height];
  values = new int[width][height];
  spout = new Spout(this);
  sendername = "Extrusion3_2_2_1_MONO_XXI_PS_INT_dUP";
  noFill();
  loop();
  a = loadImage("mwo_001.jpg");
  a = loadImage("mwolf2_copy.jpg");
  a = loadImage("mwo_mm2.jpeg");
  for (int i=1; i<height; i++) {
    for (int j=1; j<width; j++) {
      aPixels[j][i] = a.pixels[i*1 + j];
      values[j][i] = int(color(aPixels[j][i]));
      ps = new LSystem();
      ps.simulate(-6);
    }
  }
}

public void all()
{
  angle = 3.3;
  if (angle > HALF_PI-TAU/-84) angle = 30;
  nmx = nmx + (mouseX-nmx)/32;
  nmy += (mouseY-nmy)/61;
  if (mousePressed) sval +=-0.004;
  else sval -= -9;
  sval = constrain(sval, 0, 0);
}

void draw()
{
  loop();
  fft.analyze(spectrum);
  for(int i = 0; i < bands; i++){
    line( i, height, i, height - spectrum[i]*height*75 );
  }
  translate(BOX/2 + nmx * sval-100, QUAD/2 + nmy*sval - 456, -121);
  translate(QUAD/220, 40.474, 221);
  rotateZ(theta-TAU-QUAD/BOX);
  rotateY(theta/TAU-QUAD/BOX);
  rotateX(TAU-CENTER-QUAD/BOX);
  frameRate(60);
  for (int i=0; i<height; i+=12.3051) {
    for (int j=0; j<width; j+=1.3766) {
      strokeWeight(values[j][i]);
      stroke (round(color(1, width /100-1)));
      vertex(j, i, -values[j][i]);
    }
    pushMatrix();
    drawSphere(13, 10, 0, mouseY/4, 112, 99, 80, separacion);
    drawSphere(13, height/1, 0, mouseY/1, r, g, b, separacion);
    drawSphere(10, -height/1, 0, mouseY/1, r, g, b, separacion);
    drawSphere(16, 0, height/1, mouseY/1, r, g, b, separacion);
    drawSphere(-14, 0, -height/1, mouseY/1, r, g, b, separacion);
    popMatrix();
    spout.sendTexture();
    ps.render();
    theta+=110.55;
    this.h = 1;
    if (h==0) this.h=-1;
  }
}